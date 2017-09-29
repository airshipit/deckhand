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
import hashlib
import threading

from oslo_config import cfg
from oslo_db import exception as db_exception
from oslo_db import options
from oslo_db.sqlalchemy import session
from oslo_log import log as logging
from oslo_serialization import jsonutils as json
import six
import sqlalchemy.orm as sa_orm

from deckhand.db.sqlalchemy import models
from deckhand import errors
from deckhand import types
from deckhand import utils

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


def drop_db():
    models.unregister_models(get_engine())


def setup_db():
    # Ensure the DB doesn't exist before creation.
    drop_db()
    models.register_models(get_engine())


def documents_create(bucket_name, documents, session=None):
    """Create a set of documents and associated bucket.

    If no changes are detected, a new revision will not be created. This
    allows services to periodically re-register their schemas without
    creating unnecessary revisions.

    :param bucket_name: The name of the bucket with which to associate created
        documents.
    :param documents: List of documents to be created.
    :param validation_policies: List of validation policies to be created.
    :param session: Database session object.
    :returns: List of created documents in dictionary format.
    :raises DocumentExists: If the (document.schema, document.metadata.name)
        already exists in another bucket.
    """
    session = session or get_session()
    documents_to_create = _documents_create(bucket_name, documents, session)

    resp = []

    # The documents to be deleted are computed by comparing the documents for
    # the previous revision (if it exists) that belong to `bucket_name` with
    # `documents`: the difference between the former and the latter.
    document_history = [(d['schema'], d['name'])
                        for d in revision_get_documents(
                            bucket_name=bucket_name)]
    documents_to_delete = [
        h for h in document_history if h not in
        [(d['schema'], d['metadata']['name']) for d in documents]]

    # Only create a revision if any docs have been created, changed or deleted.
    if any([documents_to_create, documents_to_delete]):
        bucket = bucket_get_or_create(bucket_name)
        revision = revision_create()

    if documents_to_delete:
        LOG.debug('Deleting documents: %s.', documents_to_delete)
        deleted_documents = []

        for d in documents_to_delete:
            doc = models.Document()
            with session.begin():
                # Store bare minimum information about the document.
                doc['schema'] = d[0]
                doc['name'] = d[1]
                doc['data'] = {}
                doc['_metadata'] = {}
                doc['data_hash'] = _make_hash({})
                doc['metadata_hash'] = _make_hash({})
                doc['bucket_id'] = bucket['id']
                doc['revision_id'] = revision['id']

                # Save and mark the document as `deleted` in the database.
                doc.save(session=session)
                doc.safe_delete(session=session)
                deleted_documents.append(doc)
            resp.append(doc.to_dict())

    if documents_to_create:
        LOG.debug('Creating documents: %s.',
                  [(d['schema'], d['name']) for d in documents_to_create])
        for doc in documents_to_create:
            with session.begin():
                doc['bucket_id'] = bucket['id']
                doc['revision_id'] = revision['id']
                doc.save(session=session)
            resp.append(doc.to_dict())
    # NOTE(fmontei): The orig_revision_id is not copied into the
    # revision_id for each created document, because the revision_id here
    # should reference the just-created revision. In case the user needs
    # the original revision_id, that is returned as well.

    return resp


def _documents_create(bucket_name, values_list, session=None):
    values_list = copy.deepcopy(values_list)
    session = session or get_session()
    filters = ('name', 'schema')
    changed_documents = []

    def _document_create(values):
        document = models.Document()
        with session.begin():
            document.update(values)
        return document

    for values in values_list:
        values = _fill_in_metadata_defaults(values)
        values['is_secret'] = 'secret' in values['data']

        # Hash the document's metadata and data to later  efficiently check
        # whether those data have changed.
        values['data_hash'] = _make_hash(values['data'])
        values['metadata_hash'] = _make_hash(values['_metadata'])

        try:
            existing_document = document_get(
                raw_dict=True, **{x: values[x] for x in filters})
        except errors.DocumentNotFound:
            # Ignore bad data at this point. Allow creation to bubble up the
            # error related to bad data.
            existing_document = None

        if existing_document:
            # If the document already exists in another bucket, raise an error.
            # Ignore redundant validation policies as they are allowed to exist
            # in multiple buckets.
            if (existing_document['bucket_name'] != bucket_name and
                existing_document['schema'] != types.VALIDATION_POLICY_SCHEMA):
                raise errors.DocumentExists(
                    schema=existing_document['schema'],
                    name=existing_document['name'],
                    bucket=existing_document['bucket_name'])

            if (existing_document['data_hash'] == values['data_hash'] and
                existing_document['metadata_hash'] == values['metadata_hash']):
                # Since the document has not changed, reference the original
                # revision in which it was created. This is necessary so that
                # the correct revision history is maintained.
                if existing_document['orig_revision_id']:
                    values['orig_revision_id'] = existing_document[
                        'orig_revision_id']
                else:
                    values['orig_revision_id'] = existing_document[
                        'revision_id']

    # Create all documents, even unchanged ones, for the current revision. This
    # makes the generation of the revision diff a lot easier.
    for values in values_list:
        doc = _document_create(values)
        changed_documents.append(doc)

    return changed_documents


def _fill_in_metadata_defaults(values):
    values['_metadata'] = values.pop('metadata')
    values['name'] = values['_metadata']['name']

    if not values['_metadata'].get('storagePolicy', None):
        values['_metadata']['storagePolicy'] = 'cleartext'

    if ('layeringDefinition' in values['_metadata']
        and 'abstract' not in values['_metadata']['layeringDefinition']):
        values['_metadata']['layeringDefinition']['abstract'] = False

    return values


def _make_hash(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()


def document_get(session=None, raw_dict=False, **filters):
    """Retrieve a document from the DB.

    :param session: Database session object.
    :param raw_dict: Whether to retrieve the exact way the data is stored in
        DB if ``True``, else the way users expect the data.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :returns: Dictionary representation of retrieved document.
    :raises: DocumentNotFound if the document wasn't found.
    """
    session = session or get_session()

    # Retrieve the most recently created version of a document. Documents with
    # the same metadata.name and schema can exist across different revisions,
    # so it is necessary to use `first` instead of `one` to avoid errors.
    document = session.query(models.Document)\
        .filter_by(**filters)\
        .order_by(models.Document.created_at.desc())\
        .first()

    if not document:
        raise errors.DocumentNotFound(document=filters)

    return document.to_dict(raw_dict=raw_dict)


####################


def bucket_get_or_create(bucket_name, session=None):
    """Retrieve or create bucket.

    Retrieve the ``Bucket`` DB object by ``bucket_name`` if it exists
    or else create a new ``Bucket`` DB object by ``bucket_name``.

    :param bucket_name: Unique identifier used for creating or retrieving
        a bucket.
    :param session: Database session object.
    :returns: Dictionary representation of created/retrieved bucket.
    """
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
    """Create a revision.

    :param session: Database session object.
    :returns: Dictionary representation of created revision.
    """
    session = session or get_session()

    revision = models.Revision()
    with session.begin():
        revision.save(session=session)

    return revision.to_dict()


def revision_get(revision_id, session=None):
    """Return the specified `revision_id`.

    :param revision_id: The ID corresponding to the ``Revision`` object.
    :param session: Database session object.
    :returns: Dictionary representation of retrieved revision.
    :raises: RevisionNotFound if the revision was not found.
    """
    session = session or get_session()

    try:
        revision = session.query(models.Revision)\
            .filter_by(id=revision_id)\
            .one()\
            .to_dict()
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    revision['documents'] = _update_revision_history(revision['documents'])

    return revision


def require_revision_exists(f):
    """Decorator to require the specified revision to exist.

    Requires the wrapped function to use revision_id as the first argument. If
    revision_id is not provided, then the check is not performed.
    """
    @functools.wraps(f)
    def wrapper(revision_id=None, *args, **kwargs):
        if revision_id:
            revision_get(revision_id)
        return f(revision_id, *args, **kwargs)
    return wrapper


def _update_revision_history(documents):
    # Since documents that are unchanged across revisions need to be saved for
    # each revision, we need to ensure that the original revision is shown
    # for the document's `revision_id` to maintain the correct revision
    # history.
    for doc in documents:
        if doc['orig_revision_id']:
            doc['revision_id'] = doc['orig_revision_id']
    return documents


def _apply_filters(dct, **filters):
    """Apply filters to ``dct``.

    Apply filters in ``filters`` to the dictionary ``dct``.

    :param dct: The dictionary to check against all the ``filters``.
    :param filters: Dictionary of key-value pairs used for filtering out
        unwanted results.
    :return: True if the dictionary satisfies all the filters, else False.
    """
    def _transform_filter_bool(actual_val, filter_val):
        # Transform boolean values into string literals.
        if (isinstance(actual_val, bool)
            and isinstance(filter_val, six.string_types)):
            try:
                filter_val = ast.literal_eval(filter_val.title())
            except ValueError:
                # If not True/False, set to None to avoid matching
                # `actual_val` which is always boolean.
                filter_val = None
        return filter_val

    match = True

    for filter_key, filter_val in filters.items():
        actual_val = utils.jsonpath_parse(dct, filter_key)

        # If the filter is a list of possibilities, e.g. ['site', 'region']
        # for metadata.layeringDefinition.layer, check whether the actual
        # value is present.
        if isinstance(filter_val, (list, tuple)):
            if actual_val not in [_transform_filter_bool(actual_val, x)
                                  for x in filter_val]:
                match = False
                break
        else:
            # Else if both the filter value and the actual value in the doc
            # are dictionaries, check whether the filter dict is a subset
            # of the actual dict.
            if (isinstance(actual_val, dict)
                and isinstance(filter_val, dict)):
                is_subset = set(
                    filter_val.items()).issubset(set(actual_val.items()))
                if not is_subset:
                    match = False
                    break
            else:
                # Else both filters are string literals.
                if actual_val != _transform_filter_bool(
                        actual_val, filter_val):
                    match = False
                    break

    return match


def revision_get_all(session=None, **filters):
    """Return list of all revisions.

    :param session: Database session object.
    :returns: List of dictionary representations of retrieved revisions.
    """
    session = session or get_session()
    revisions = session.query(models.Revision)\
        .all()

    result = []
    for revision in revisions:
        revision_dict = revision.to_dict()
        if _apply_filters(revision_dict, **filters):
            revision_dict['documents'] = _update_revision_history(
                revision_dict['documents'])
            result.append(revision_dict)

    return result


def revision_delete_all(session=None):
    """Delete all revisions.

    :param session: Database session object.
    :returns: None
    """
    session = session or get_session()
    session.query(models.Revision)\
        .delete(synchronize_session=False)


def _filter_revision_documents(documents, unique_only, **filters):
    """Return the list of documents that match filters.

    :param unique_only: Return only unique documents if ``True``.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :returns: List of documents that match specified filters.
    """
    # TODO(fmontei): Implement this as an sqlalchemy query.
    filtered_documents = {}
    unique_filters = ('name', 'schema')

    for document in documents:
        # NOTE(fmontei): Only want to include non-validation policy documents
        # for this endpoint.
        if document['schema'] == types.VALIDATION_POLICY_SCHEMA:
            continue

        if _apply_filters(document, **filters):
            # Filter out redundant documents from previous revisions, i.e.
            # documents schema and metadata.name are repeated.
            if unique_only:
                unique_key = tuple(
                    [document[filter] for filter in unique_filters])
            else:
                unique_key = document['id']
            if unique_key not in filtered_documents:
                filtered_documents[unique_key] = document

    # TODO(fmontei): Sort by user-specified parameter.
    return sorted(filtered_documents.values(), key=lambda d: d['created_at'])


@require_revision_exists
def revision_get_documents(revision_id=None, include_history=True,
                           unique_only=True, session=None, **filters):
    """Return the documents that match filters for the specified `revision_id`.

    :param revision_id: The ID corresponding to the ``Revision`` object. If the
        ID is ``None``, then retrieve the latest revision, if one exists.
    :param include_history: Return all documents for revision history prior
        and up to current revision, if ``True``. Default is ``True``.
    :param unique_only: Return only unique documents if ``True. Default is
        ``True``.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :param session: Database session object.
    :returns: All revision documents for ``revision_id`` that match the
        ``filters``, including document revision history if applicable.
    :raises: RevisionNotFound if the revision was not found.
    """
    session = session or get_session()
    revision_documents = []

    try:
        if revision_id:
            revision = session.query(models.Revision)\
                .filter_by(id=revision_id)\
                .one()
        else:
            # If no revision_id is specified, grab the newest one.
            revision = session.query(models.Revision)\
                .order_by(models.Revision.created_at.desc())\
                .first()

        revision_documents = (revision.to_dict()['documents']
                              if revision else [])

        if include_history and revision:
            older_revisions = session.query(models.Revision)\
                .filter(models.Revision.created_at < revision.created_at)\
                .order_by(models.Revision.created_at)\
                .all()

            # Include documents from older revisions in response body.
            for older_revision in older_revisions:
                revision_documents.extend(
                    older_revision.to_dict()['documents'])
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    revision_documents = _update_revision_history(revision_documents)

    filtered_documents = _filter_revision_documents(
        revision_documents, unique_only, **filters)

    return filtered_documents


# NOTE(fmontei): No need to include `@require_revision_exists` decorator as
# the this function immediately calls `revision_get_documents` for both
# revision IDs, which has the decorator applied to it.
def revision_diff(revision_id, comparison_revision_id):
    """Generate the diff between two revisions.

    Generate the diff between the two revisions: `revision_id` and
    `comparison_revision_id`. A basic comparison of the revisions in terms of
    how the buckets involved have changed is generated. Only buckets with
    existing documents in either of the two revisions in question will be
    reported.

    The ordering of the two revision IDs is interchangeable, i.e. no matter
    the order, the same result is generated.

    The differences include:

        - "created": A bucket has been created between the revisions.
        - "deleted": A bucket has been deleted between the revisions.
        - "modified": A bucket has been modified between the revisions.
        - "unmodified": A bucket remains unmodified between the revisions.

    :param revision_id: ID of the first revision.
    :param comparison_revision_id: ID of the second revision.
    :returns: A dictionary, keyed with the bucket IDs, containing any of the
        differences enumerated above.

    Examples::

        # GET /api/v1.0/revisions/6/diff/3
        bucket_a: created
        bucket_b: deleted
        bucket_c: modified
        bucket_d: unmodified

        # GET /api/v1.0/revisions/0/diff/6
        bucket_a: created
        bucket_c: created
        bucket_d: created

        # GET /api/v1.0/revisions/6/diff/6
        bucket_a: unmodified
        bucket_c: unmodified
        bucket_d: unmodified

        # GET /api/v1.0/revisions/0/diff/0
        {}
    """
    # Retrieve document history for each revision. Since `revision_id` of 0
    # doesn't exist, treat it as a special case: empty list.
    docs = (revision_get_documents(revision_id,
                                   include_history=True,
                                   unique_only=False)
            if revision_id != 0 else [])
    comparison_docs = (revision_get_documents(comparison_revision_id,
                                              include_history=True,
                                              unique_only=False)
                       if comparison_revision_id != 0 else [])

    # Remove each deleted document and its older counterparts because those
    # documents technically don't exist.
    for doc_collection in (docs, comparison_docs):
        for doc in copy.copy(doc_collection):
            if doc['deleted']:
                docs_to_delete = filter(
                    lambda d:
                        (d['schema'], d['name']) ==
                        (doc['schema'], doc['name'])
                        and d['created_at'] <= doc['deleted_at'],
                    doc_collection)
                for d in list(docs_to_delete):
                    doc_collection.remove(d)

    revision = revision_get(revision_id) if revision_id != 0 else None
    comparison_revision = (revision_get(comparison_revision_id)
                           if comparison_revision_id != 0 else None)

    # Each dictionary below, keyed with the bucket's name, references the list
    # of documents related to each bucket.
    buckets = {}
    comparison_buckets = {}
    for doc in docs:
        buckets.setdefault(doc['bucket_name'], [])
        buckets[doc['bucket_name']].append(doc)
    for doc in comparison_docs:
        comparison_buckets.setdefault(doc['bucket_name'], [])
        comparison_buckets[doc['bucket_name']].append(doc)

    # `shared_buckets` references buckets shared by both `revision_id` and
    # `comparison_revision_id` -- i.e. their intersection.
    shared_buckets = set(buckets.keys()).intersection(
        comparison_buckets.keys())
    # `unshared_buckets` references buckets not shared by both `revision_id`
    # and `comparison_revision_id` -- i.e. their non-intersection.
    unshared_buckets = set(buckets.keys()).union(
        comparison_buckets.keys()) - shared_buckets

    result = {}

    def _compare_buckets(b1, b2):
        # Checks whether buckets' documents are identical.
        return (sorted([(d['data_hash'], d['metadata_hash']) for d in b1]) ==
                sorted([(d['data_hash'], d['metadata_hash']) for d in b2]))

    # If the list of documents for each bucket is indentical, then the result
    # is "unmodified", else "modified".
    for bucket_name in shared_buckets:
        unmodified = _compare_buckets(buckets[bucket_name],
                                      comparison_buckets[bucket_name])
        result[bucket_name] = 'unmodified' if unmodified else 'modified'

    for bucket_name in unshared_buckets:
        # If neither revision has documents, then there's nothing to compare.
        # This is always True for revision_id == comparison_revision_id == 0.
        if not any([revision, comparison_revision]):
            break
        # Else if one revision == 0 and the other revision != 0, then the
        # bucket has been created. Which is zero or non-zero doesn't matter.
        elif not all([revision, comparison_revision]):
            result[bucket_name] = 'created'
        # Else if `revision` is newer than `comparison_revision`, then if the
        # `bucket_name` isn't in the `revision` buckets, then it has been
        # deleted. Otherwise it has been created.
        elif revision['created_at'] > comparison_revision['created_at']:
            if bucket_name not in buckets:
                result[bucket_name] = 'deleted'
            elif bucket_name not in comparison_buckets:
                result[bucket_name] = 'created'
        # Else if `comparison_revision` is newer than `revision`, then if the
        # `bucket_name` isn't in the `revision` buckets, then it has been
        # created. Otherwise it has been deleted.
        else:
            if bucket_name not in buckets:
                result[bucket_name] = 'created'
            elif bucket_name not in comparison_buckets:
                result[bucket_name] = 'deleted'

    return result


####################


@require_revision_exists
def revision_tag_create(revision_id, tag, data=None, session=None):
    """Create a revision tag.

    If a tag already exists by name ``tag``, the request is ignored.

    :param revision_id: ID corresponding to ``Revision`` DB object.
    :param tag: Name of the revision tag.
    :param data: Dictionary of data to be associated with tag.
    :param session: Database session object.
    :returns: The tag that was created if not already present in the database,
        else None.
    :raises RevisionTagBadFormat: If data is neither None nor dictionary.
    """
    session = session or get_session()
    tag_model = models.RevisionTag()

    if data and not isinstance(data, dict):
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

    :param revision_id: ID corresponding to ``Revision`` DB object.
    :param tag: Name of the revision tag.
    :param session: Database session object.
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

    :param revision_id: ID corresponding to ``Revision`` DB object.
    :param tag: Name of the revision tag.
    :param session: Database session object.
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

    :param revision_id: ID corresponding to ``Revision`` DB object.
    :param tag: Name of the revision tag.
    :param session: Database session object.
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

    :param revision_id: ID corresponding to ``Revision`` DB object.
    :param session: Database session object.
    :returns: None
    """
    session = session or get_session()
    session.query(models.RevisionTag)\
        .filter_by(revision_id=revision_id)\
        .delete(synchronize_session=False)


####################


@require_revision_exists
def revision_rollback(revision_id, session=None):
    """Rollback the latest revision to revision specified by ``revision_id``.

    Rolls back the latest revision to the revision specified by ``revision_id``
    thereby creating a new, carbon-copy revision.

    :param revision_id: Revision ID to which to rollback.
    :returns: The newly created revision.
    """
    session = session or get_session()

    # We know that the last revision exists, since require_revision_exists
    # ensures revision_id exists, which at the very least is the last revision.
    latest_revision = session.query(models.Revision)\
        .order_by(models.Revision.created_at.desc())\
        .first()
    latest_revision_hashes = [
        (d['data_hash'], d['metadata_hash'])
        for d in latest_revision['documents']]

    # If the rollback revision is the same as the latest revision, then there's
    # no point in rolling back.
    if latest_revision['id'] == revision_id:
        raise errors.InvalidRollback(revision_id=revision_id)

    orig_revision = revision_get(revision_id, session=session)

    # A mechanism for determining whether a particular document has changed
    # between revisions. Keyed with the document_id, the value is True if
    # it has changed, else False.
    doc_diff = {}
    for orig_doc in orig_revision['documents']:
        if ((orig_doc['data_hash'], orig_doc['metadata_hash'])
            not in latest_revision_hashes):
            doc_diff[orig_doc['id']] = True
        else:
            doc_diff[orig_doc['id']] = False

    # If no changes have been made between the target revision to rollback to
    # and the latest revision, raise an exception.
    if set(doc_diff.values()) == set([False]):
        raise errors.InvalidRollback(revision_id=revision_id)

    # Create the new revision,
    new_revision = models.Revision()
    with session.begin():
        new_revision.save(session=session)

    # Create the documents for the revision.
    for orig_document in orig_revision['documents']:
        orig_document['revision_id'] = new_revision['id']
        orig_document['_metadata'] = orig_document.pop('metadata')

        new_document = models.Document()
        new_document.update({x: orig_document[x] for x in (
            'name', '_metadata', 'data', 'data_hash', 'metadata_hash',
            'schema', 'bucket_id')})
        new_document['revision_id'] = new_revision['id']

        # If the document has changed, then use the revision_id of the new
        # revision, otherwise use the original revision_id to preserve the
        # revision history.
        if doc_diff[orig_document['id']]:
            new_document['orig_revision_id'] = new_revision['id']
        else:
            new_document['orig_revision_id'] = orig_revision['id']

        with session.begin():
            new_document.save(session=session)

    new_revision = new_revision.to_dict()
    new_revision['documents'] = _update_revision_history(
        new_revision['documents'])

    return new_revision
