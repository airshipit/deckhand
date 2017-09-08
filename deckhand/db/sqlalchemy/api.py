# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Defines interface for DB access."""

import ast
import copy
import functools
import threading

from oslo_config import cfg
from oslo_db import exception as db_exception
from oslo_db import options
from oslo_db.sqlalchemy import session
from oslo_log import log as logging
import six
import sqlalchemy.orm as sa_orm

from deckhand.db.sqlalchemy import models
from deckhand import errors
from deckhand import types
from deckhand import utils

sa_logger = None
LOG = logging.getLogger(__name__)

CONF = cfg.CONF

options.set_defaults(CONF)

_FACADE = None
_LOCK = threading.Lock()


def _retry_on_deadlock(exc):
    """Decorator to retry a DB API call if Deadlock was received."""

    if isinstance(exc, db_exception.DBDeadlock):
        LOG.warn("Deadlock detected. Retrying...")
        return True
    return False


def _create_facade_lazily():
    global _LOCK, _FACADE
    if _FACADE is None:
        with _LOCK:
            if _FACADE is None:
                _FACADE = session.EngineFacade.from_config(
                    CONF, sqlite_fk=True)
    return _FACADE


def get_engine():
    facade = _create_facade_lazily()
    return facade.get_engine()


def get_session(autocommit=True, expire_on_commit=False):
    facade = _create_facade_lazily()
    return facade.get_session(autocommit=autocommit,
                              expire_on_commit=expire_on_commit)


def clear_db_env():
    """Unset global configuration variables for database."""
    global _FACADE
    _FACADE = None


def setup_db():
    models.register_models(get_engine())


def drop_db():
    models.unregister_models(get_engine())


def documents_create(bucket_name, documents, session=None):
    session = session or get_session()
    documents_created = _documents_create(documents, session)

    if documents_created:
        bucket = bucket_get_or_create(bucket_name)
        revision = revision_create()

        for doc in documents_created:
            with session.begin():
                doc['bucket_id'] = bucket['name']
                doc['revision_id'] = revision['id']
                doc.save(session=session)

    return [d.to_dict() for d in documents_created]


def _documents_create(values_list, session=None):
    """Create a set of documents and associated schema.

    If no changes are detected, a new revision will not be created. This
    allows services to periodically re-register their schemas without
    creating unnecessary revisions.

    :param values_list: List of documents to be saved.
    """
    values_list = copy.deepcopy(values_list)
    session = session or get_session()
    filters = [c for c in models.Document.UNIQUE_CONSTRAINTS
               if c != 'revision_id']

    documents_to_change = []
    changed_documents = []

    def _document_changed(existing_document):
        # The document has changed if at least one value in ``values`` differs.
        for key, val in values.items():
            if val != existing_document[key]:
                return True
        return False

    def _document_create(values):
        document = models.Document()
        with session.begin():
            document.update(values)
        return document

    for values in values_list:
        values['_metadata'] = values.pop('metadata')
        values['name'] = values['_metadata']['name']

        # NOTE(fmontei): Database requires that the 'data' column be a dict, so
        # coerce the secret into a dictionary if it already isn't one.
        if values['schema'] in (types.CERTIFICATE_SCHEMA,
                                types.CERTIFICATE_KEY_SCHEMA,
                                types.PASSPHRASE_SCHEMA):
            if not isinstance(values['data'], dict):
                values['data'] = {'secret': values['data']}

        try:
            existing_document = document_get(
                raw_dict=True, **{c: values[c] for c in filters})
        except errors.DocumentNotFound:
            # Ignore bad data at this point. Allow creation to bubble up the
            # error related to bad data.
            existing_document = None

        if not existing_document:
            documents_to_change.append(values)
        elif existing_document and _document_changed(existing_document):
            documents_to_change.append(values)

    if documents_to_change:
        for values in documents_to_change:
            doc = _document_create(values)
            changed_documents.append(doc)

    return changed_documents


def document_get(session=None, raw_dict=False, **filters):
    session = session or get_session()
    if 'document_id' in filters:
        filters['id'] = filters.pop('document_id')

    try:
        document = session.query(models.Document)\
            .filter_by(**filters)\
            .one()
    except sa_orm.exc.NoResultFound:
        raise errors.DocumentNotFound(document=filters)

    return document.to_dict(raw_dict=raw_dict)


####################


def bucket_get_or_create(bucket_name, session=None):
    session = session or get_session()

    try:
        bucket = session.query(models.Bucket)\
            .filter_by(name=bucket_name)\
            .one()
    except sa_orm.exc.NoResultFound:
        bucket = models.Bucket()
        with session.begin():
            bucket.update({'name': bucket_name})
            bucket.save(session=session)

    return bucket.to_dict()


####################

def revision_create(session=None):
    session = session or get_session()

    revision = models.Revision()
    with session.begin():
        revision.save(session=session)

    return revision.to_dict()


def revision_get(revision_id, session=None):
    """Return the specified `revision_id`.

    :raises: RevisionNotFound if the revision was not found.
    """
    session = session or get_session()

    try:
        revision = session.query(models.Revision)\
            .filter_by(id=revision_id)\
            .one()
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    return revision.to_dict()


def require_revision_exists(f):
    """Decorator to require the specified revision to exist.
    Requires the wrapped function to use revision_id as the first argument.
    """

    @functools.wraps(f)
    def wrapper(revision_id, *args, **kwargs):
        revision_get(revision_id)
        return f(revision_id, *args, **kwargs)
    return wrapper


def revision_get_all(session=None):
    """Return list of all revisions."""
    session = session or get_session()
    revisions = session.query(models.Revision)\
        .all()
    return [r.to_dict() for r in revisions]


def revision_delete_all(session=None):
    """Delete all revisions."""
    session = session or get_session()
    session.query(models.Revision)\
        .delete(synchronize_session=False)


def revision_get_documents(revision_id, session=None, **filters):
    """Return the documents that match filters for the specified `revision_id`.

    Deleted documents are not included unless deleted=True is provided in
    ``filters``.

    :raises: RevisionNotFound if the revision was not found.
    """
    session = session or get_session()
    try:
        revision = session.query(models.Revision)\
            .filter_by(id=revision_id)\
            .one()
        older_revisions = session.query(models.Revision)\
            .filter(models.Revision.created_at < revision.created_at)\
            .order_by(models.Revision.created_at)\
            .all()
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    document_history = []
    for rev in ([revision] + older_revisions):
        document_history.extend(rev.to_dict()['documents'])

    filtered_documents = _filter_revision_documents(
        document_history, **filters)

    return filtered_documents


def _filter_revision_documents(documents, **filters):
    """Return the list of documents that match filters.

    :returns: List of documents that match specified filters.
    """
    # TODO(fmontei): Implement this as an sqlalchemy query.
    filtered_documents = {}
    unique_filters = [c for c in models.Document.UNIQUE_CONSTRAINTS
                      if c != 'revision_id']

    for document in documents:
        # NOTE(fmontei): Only want to include non-validation policy documents
        # for this endpoint.
        if document['schema'] in types.VALIDATION_POLICY_SCHEMA:
            continue
        match = True

        for filter_key, filter_val in filters.items():
            actual_val = utils.multi_getattr(filter_key, document)

            if (isinstance(actual_val, bool)
                and isinstance(filter_val, six.string_types)):
                try:
                    filter_val = ast.literal_eval(filter_val.title())
                except ValueError:
                    # If not True/False, set to None to avoid matching
                    # `actual_val` which is always boolean.
                    filter_val = None

            if actual_val != filter_val:
                match = False

        if match:
            # Filter out redundant documents from previous revisions, i.e.
            # documents schema and metadata.name are repeated.
            unique_key = tuple([document[filter] for filter in unique_filters])
            if unique_key not in filtered_documents:
                filtered_documents[unique_key] = document

    return sorted(filtered_documents.values(), key=lambda d: d['created_at'])


####################


@require_revision_exists
def revision_tag_create(revision_id, tag, data=None, session=None):
    """Create a revision tag.

    :returns: The tag that was created if not already present in the database,
        else None.
    """
    session = session or get_session()
    tag_model = models.RevisionTag()

    try:
        assert not data or isinstance(data, dict)
    except AssertionError:
        raise errors.RevisionTagBadFormat(data=data)

    try:
        with session.begin():
            tag_model.update(
                {'tag': tag, 'data': data, 'revision_id': revision_id})
            tag_model.save(session=session)
        resp = tag_model.to_dict()
    except db_exception.DBDuplicateEntry:
        resp = None

    return resp


@require_revision_exists
def revision_tag_get(revision_id, tag, session=None):
    """Retrieve tag details.

    :returns: None
    :raises RevisionTagNotFound: If ``tag`` for ``revision_id`` was not found.
    """
    session = session or get_session()

    try:
        tag = session.query(models.RevisionTag)\
            .filter_by(tag=tag, revision_id=revision_id)\
            .one()
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionTagNotFound(tag=tag, revision=revision_id)

    return tag.to_dict()


@require_revision_exists
def revision_tag_get_all(revision_id, session=None):
    """Return list of tags for a revision.

    :returns: List of tags for ``revision_id``, ordered by the tag name by
        default.
    """
    session = session or get_session()
    tags = session.query(models.RevisionTag)\
        .filter_by(revision_id=revision_id)\
        .order_by(models.RevisionTag.tag)\
        .all()
    return [t.to_dict() for t in tags]


@require_revision_exists
def revision_tag_delete(revision_id, tag, session=None):
    """Delete a specific tag for a revision.

    :returns: None
    """
    session = session or get_session()
    result = session.query(models.RevisionTag)\
                .filter_by(tag=tag, revision_id=revision_id)\
                .delete(synchronize_session=False)
    if result == 0:
        raise errors.RevisionTagNotFound(tag=tag, revision=revision_id)


@require_revision_exists
def revision_tag_delete_all(revision_id, session=None):
    """Delete all tags for a revision.

    :returns: None
    """
    session = session or get_session()
    session.query(models.RevisionTag)\
        .filter_by(revision_id=revision_id)\
        .delete(synchronize_session=False)
