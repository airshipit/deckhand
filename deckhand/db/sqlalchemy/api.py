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
import datetime
import threading

from oslo_config import cfg
from oslo_db import exception as db_exception
from oslo_db import options
from oslo_db.sqlalchemy import session
from oslo_log import log as logging
from oslo_utils import excutils
import six
from six.moves import range
import sqlalchemy
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import desc
from sqlalchemy import MetaData, Table
import sqlalchemy.orm as sa_orm
from sqlalchemy import sql
import sqlalchemy.sql as sa_sql

from deckhand.db.sqlalchemy import models
from deckhand import errors
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


def _validate_db_int(**kwargs):
    """Make sure that all arguments are less than or equal to 2 ** 31 - 1.
    This limitation is introduced because databases stores INT in 4 bytes.
    If the validation fails for some argument, exception. Invalid is raised
    with appropriate information.
    """
    max_int = (2 ** 31) - 1

    for param_key, param_value in kwargs.items():
        if param_value and param_value > max_int:
            msg = _("'%(param)s' value out of range, "
                    "must not exceed %(max)d.") % {"param": param_key,
                                                   "max": max_int}
            raise exception.Invalid(msg)


def clear_db_env():
    """Unset global configuration variables for database."""
    global _FACADE
    _FACADE = None


def setup_db():
    models.register_models(get_engine())


def drop_db():
    models.unregister_models(get_engine())


def documents_create(documents, session=None):
    """Create a set of documents."""
    created_docs = [document_create(doc, session) for doc in documents]
    return created_docs


def documents_create(values_list, session=None):
    """Create a set of documents and associated schema.

    If no changes are detected, a new revision will not be created. This
    allows services to periodically re-register their schemas without
    creating unnecessary revisions.
    """
    values_list = copy.deepcopy(values_list)
    session = session or get_session()
    filters = models.Document.UNIQUE_CONSTRAINTS

    do_create = False
    documents_created = []

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
            document.save(session=session)
        return document.to_dict()

    for values in values_list:
        values['_metadata'] = values.pop('metadata')
        values['name'] = values['_metadata']['name']
    
        try:
            existing_document = document_get(
                raw_dict=True,
                **{c: values[c] for c in filters if c != 'revision_id'})
        except db_exception.DBError:
            # Ignore bad data at this point. Allow creation to bubble up the
            # error related to bad data.
            existing_document = None

        if not existing_document:
            do_create = True
        elif existing_document and _document_changed(existing_document):
            do_create = True

    if do_create:
        revision = revision_create()

        for values in values_list:
            values['revision_id'] = revision['id']
            doc = _document_create(values)
            documents_created.append(doc)

    return documents_created


def document_get(session=None, raw_dict=False, **filters):
    session = session or get_session()
    document = session.query(models.Document).filter_by(**filters).first()
    return document.to_dict(raw_dict=raw_dict) if document else {}


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
        revision = session.query(models.Revision).filter_by(
            id=revision_id).one().to_dict()
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    return revision


def revision_get_all(session=None):
    """Return list of all revisions."""
    session = session or get_session()
    revisions = session.query(models.Revision).all()
    revisions_resp = [r.to_dict() for r in revisions]

    for revision in revisions_resp:
        revision['count'] = len(revision.pop('documents'))

    return revisions_resp


def revision_get_documents(revision_id, session=None, **filters):
    """Return the documents that match filters for the specified `revision_id`.

    :raises: RevisionNotFound if the revision was not found.
    """
    session = session or get_session()
    try:
        revision = session.query(models.Revision).filter_by(
            id=revision_id).one().to_dict()
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    filtered_documents = _filter_revision_documents(
        revision['documents'], **filters)
    return filtered_documents


def _filter_revision_documents(documents, **filters):
    """Return the list of documents that match filters.

    :returns: list of documents that match specified filters.
    """
    # TODO: Implement this as an sqlalchemy query.
    filtered_documents = []

    for document in documents:
        match = True

        for filter_key, filter_val in filters.items():
            actual_val = utils.multi_getattr(filter_key, document)

            if (isinstance(actual_val, bool)
                and isinstance(filter_val, six.text_type)):
                try:
                    filter_val = ast.literal_eval(filter_val.title())
                except ValueError:
                    # If not True/False, set to None to avoid matching
                    # `actual_val` which is always boolean.
                    filter_val = None

            if actual_val != filter_val:
                match = False

        if match:
            filtered_documents.append(document)

    return filtered_documents
