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
import sqlalchemy.orm as sa_orm
from sqlalchemy import text

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


def raw_query(query, **kwargs):
    """Execute a raw query against the database."""

    # Cast all the strings that represent integers to integers because type
    # matters when using ``bindparams``.
    for key, val in kwargs.items():
        if key.endswith('_id'):
            try:
                val = int(val)
                kwargs[key] = val
            except ValueError:
                pass

    stmt = text(query)
    stmt = stmt.bindparams(**kwargs)
    return get_engine().execute(stmt)


def require_unique_document_schema(schema=None):
    """Decorator to enforce only one singleton document exists in the system.

    An example of a singleton document is a ``LayeringPolicy`` document.

    Only one singleton document can exist within the system at any time. It is
    an error to attempt to insert a new document with the same ``schema`` if it
    has a different ``metadata.name`` than the existing document.

    A singleton document that already exists can be updated, if the document
    that is passed in has the same name/schema as the existing one.

    The existing singleton document can be replaced by first deleting it
    and only then creating a new one.

    :raises SingletonDocumentConflict: if a singleton document in the system
        already exists and any of the documents to be created has the same
        ``schema`` but has a ``metadata.name`` that differs from the one
        already registered.
    """
    def decorator(f):
        if schema not in types.DOCUMENT_SCHEMA_TYPES:
            raise errors.DeckhandException(
                'Unrecognized document schema %s.' % schema)

        @functools.wraps(f)
        def wrapper(bucket_name, documents, *args, **kwargs):
            existing_documents = revision_documents_get(
                schema=schema, deleted=False, include_history=False)
            existing_document_names = [x['name'] for x in existing_documents]
            conflicting_names = [
                x['metadata']['name'] for x in documents
                if x['metadata']['name'] not in existing_document_names and
                   x['schema'].startswith(schema)]
            if existing_document_names and conflicting_names:
                raise errors.SingletonDocumentConflict(
                    document=existing_document_names[0],
                    conflict=conflicting_names)
            return f(bucket_name, documents, *args, **kwargs)
        return wrapper
    return decorator


@require_unique_document_schema(types.LAYERING_POLICY_SCHEMA)
def documents_create(bucket_name, documents, validations=None,
                     session=None):
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
                        for d in revision_documents_get(
                            bucket_name=bucket_name)]
    documents_to_delete = [
        h for h in document_history if h not in
        [(d['schema'], d['metadata']['name']) for d in documents]]

    # Only create a revision if any docs have been created, changed or deleted.
    if any([documents_to_create, documents_to_delete]):
        bucket = bucket_get_or_create(bucket_name)
        revision = revision_create()
        if validations:
            for validation in validations:
                validation_create(revision['id'], validation['name'],
                                  validation)

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
        values.setdefault('data', {})
        values = _fill_in_metadata_defaults(values)

        # Hash the document's metadata and data to later  efficiently check
        # whether those data have changed.
        values['data_hash'] = _make_hash(values['data'])
        values['metadata_hash'] = _make_hash(values['_metadata'])

        try:
            existing_document = document_get(
                raw_dict=True, deleted=False, revision_id='latest',
                **{x: values[x] for x in filters})
        except errors.DocumentNotFound:
            # Ignore bad data at this point. Allow creation to bubble up the
            # error related to bad data.
            existing_document = None

        if existing_document:
            # If the document already exists in another bucket, raise an error.
            # Ignore redundant validation policies as they are allowed to exist
            # in multiple buckets.
            if (existing_document['bucket_name'] != bucket_name and
                not existing_document['schema'].startswith(
                    types.VALIDATION_POLICY_SCHEMA)):
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

    if 'layeringDefinition' not in values['_metadata']:
        values['_metadata'].setdefault('layeringDefinition', {})

    if 'abstract' not in values['_metadata']['layeringDefinition']:
        values['_metadata']['layeringDefinition']['abstract'] = False

    return values


def _make_hash(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()


def document_get(session=None, raw_dict=False, revision_id=None, **filters):
    """Retrieve the first document for ``revision_id`` that match ``filters``.

    :param session: Database session object.
    :param raw_dict: Whether to retrieve the exact way the data is stored in
        DB if ``True``, else the way users expect the data.
    :param revision_id: The ID corresponding to the ``Revision`` object. If the
        it is "latest", then retrieve the latest revision, if one exists.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :returns: Dictionary representation of retrieved document.
    :raises: DocumentNotFound if the document wasn't found.
    """
    session = session or get_session()

    if revision_id == 'latest':
        revision = session.query(models.Revision)\
            .order_by(models.Revision.created_at.desc())\
            .first()
        if revision:
            filters['revision_id'] = revision.id
    elif revision_id:
        filters['revision_id'] = revision_id

    # TODO(fmontei): Currently Deckhand doesn't support filtering by nested
    # JSON fields via sqlalchemy. For now, filter the documents using all
    # "regular" filters via sqlalchemy and all nested filters via Python.
    nested_filters = {}
    for f in filters.copy():
        if any([x in f for x in ('.', 'schema')]):
            nested_filters.setdefault(f, filters.pop(f))

    # Documents with the the same metadata.name and schema can exist across
    # different revisions, so it is necessary to order documents by creation
    # date, then return the first document that matches all desired filters.
    documents = session.query(models.Document)\
        .filter_by(**filters)\
        .order_by(models.Document.created_at.desc())\
        .all()

    for doc in documents:
        d = doc.to_dict(raw_dict=raw_dict)
        if utils.deepfilter(d, **nested_filters):
            return d

    filters.update(nested_filters)
    raise errors.DocumentNotFound(document=filters)


def document_get_all(session=None, raw_dict=False, revision_id=None,
                     **filters):
    """Retrieve all documents for ``revision_id`` that match ``filters``.

    :param session: Database session object.
    :param raw_dict: Whether to retrieve the exact way the data is stored in
        DB if ``True``, else the way users expect the data.
    :param revision_id: The ID corresponding to the ``Revision`` object. If the
        it is "latest", then retrieve the latest revision, if one exists.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :returns: Dictionary representation of each retrieved document.
    """
    session = session or get_session()

    if revision_id == 'latest':
        revision = session.query(models.Revision)\
            .order_by(models.Revision.created_at.desc())\
            .first()
        if revision:
            filters['revision_id'] = revision.id
    elif revision_id:
        filters['revision_id'] = revision_id

    # TODO(fmontei): Currently Deckhand doesn't support filtering by nested
    # JSON fields via sqlalchemy. For now, filter the documents using all
    # "regular" filters via sqlalchemy and all nested filters via Python.
    nested_filters = {}
    for f in filters.copy():
        if any([x in f for x in ('.', 'schema')]):
            nested_filters.setdefault(f, filters.pop(f))

    # Retrieve the most recently created documents for the revision, because
    # documents with the same metadata.name and schema can exist across
    # different revisions.
    documents = session.query(models.Document)\
        .filter_by(**filters)\
        .order_by(models.Document.created_at.desc())\
        .all()

    final_documents = []
    for doc in documents:
        d = doc.to_dict(raw_dict=raw_dict)
        if utils.deepfilter(d, **nested_filters):
            final_documents.append(d)

    return final_documents


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


def revision_get(revision_id=None, session=None):
    """Return the specified `revision_id`.

    :param revision_id: The ID corresponding to the ``Revision`` object.
    :param session: Database session object.
    :returns: Dictionary representation of retrieved revision.
    :raises RevisionNotFound: if the revision was not found.
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


def revision_get_latest(session=None):
    """Return the latest revision.

    :param session: Database session object.
    :returns: Dictionary representation of latest revision.
    :raises RevisionNotFound: if the latest revision was not found.
    """
    session = session or get_session()

    latest_revision = session.query(models.Revision)\
        .order_by(models.Revision.created_at.desc())\
        .first()
    if not latest_revision:
        raise errors.RevisionNotFound(revision='latest')

    latest_revision = latest_revision.to_dict()

    latest_revision['documents'] = _update_revision_history(
        latest_revision['documents'])

    return latest_revision


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
        if utils.deepfilter(revision_dict, **filters):
            revision_dict['documents'] = _update_revision_history(
                revision_dict['documents'])
            result.append(revision_dict)

    return result


def revision_delete_all():
    """Delete all revisions and resets primary key index back to 1 for each
    table in the database.

    .. warning::

        Effectively purges all data from database.

    :param session: Database session object.
    :returns: None
    """
    engine = get_engine()
    if engine.name == 'postgresql':
        # NOTE(fmontei): While cascade should delete all data from all tables,
        # we also need to reset the index to 1 for each table.
        for table in ['buckets', 'revisions', 'revision_tags', 'documents',
                      'validations']:
            engine.execute(
                text("TRUNCATE TABLE %s RESTART IDENTITY CASCADE;" % table)
                .execution_options(autocommit=True))
    else:
        raw_query("DELETE FROM revisions;")


def _exclude_deleted_documents(documents):
    """Excludes all documents with ``deleted=True`` field including all
    documents earlier in the revision history with the same `metadata.name`
    and `schema` from ``documents``.
    """
    for doc in copy.copy(documents):
        if doc['deleted']:
            docs_to_delete = [
                d for d in documents if
                    (d['schema'], d['name']) == (doc['schema'], doc['name'])
                    and d['created_at'] <= doc['deleted_at']
            ]
            for d in list(docs_to_delete):
                documents.remove(d)
    return documents


def _filter_revision_documents(documents, unique_only, **filters):
    """Return the list of documents that match filters.

    :param documents: List of documents to apply ``filters`` to.
    :param unique_only: Return only unique documents if ``True``.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :returns: List of documents that match specified filters.
    """
    # TODO(fmontei): Implement this as an sqlalchemy query.
    filtered_documents = {}
    unique_filters = ('schema', 'name')
    exclude_deleted = filters.pop('deleted', None) is False

    if exclude_deleted:
        documents = _exclude_deleted_documents(documents)

    for document in documents:
        if utils.deepfilter(document, **filters):
            # Filter out redundant documents from previous revisions, i.e.
            # documents schema and metadata.name are repeated.
            if unique_only:
                unique_key = tuple(
                    [document[filter] for filter in unique_filters])
            else:
                unique_key = document['id']
            if unique_key not in filtered_documents:
                filtered_documents[unique_key] = document

    return list(filtered_documents.values())


@require_revision_exists
def revision_documents_get(revision_id=None, include_history=True,
                           unique_only=True, session=None, **filters):
    """Return the documents that match filters for the specified `revision_id`.

    :param revision_id: The ID corresponding to the ``Revision`` object. If the
        ID is ``None``, then retrieve the latest revision, if one exists.
    :param include_history: Return all documents for revision history prior
        and up to current revision, if ``True``. Default is ``True``.
    :param unique_only: Return only unique documents if ``True. Default is
        ``True``.
    :param session: Database session object.
    :param filters: Key-value pairs used for filtering out revision documents.
    :returns: All revision documents for ``revision_id`` that match the
        ``filters``, including document revision history if applicable.
    :raises RevisionNotFound: if the revision was not found.
    """
    session = session or get_session()
    revision_documents = []

    try:
        if revision_id:
            revision = session.query(models.Revision)\
                .filter_by(id=revision_id)\
                .one()
        else:
            # If no revision_id is specified, grab the latest one.
            revision = session.query(models.Revision)\
                .order_by(models.Revision.created_at.desc())\
                .first()

        if revision:
            revision_documents = revision.to_dict()['documents']
            if include_history:
                relevant_revisions = session.query(models.Revision)\
                    .filter(models.Revision.created_at < revision.created_at)\
                    .order_by(models.Revision.created_at)\
                    .all()
                # Include documents from older revisions in response body.
                for relevant_revision in relevant_revisions:
                    revision_documents.extend(
                        relevant_revision.to_dict()['documents'])
    except sa_orm.exc.NoResultFound:
        raise errors.RevisionNotFound(revision=revision_id)

    revision_documents = _update_revision_history(revision_documents)

    filtered_documents = _filter_revision_documents(
        revision_documents, unique_only, **filters)

    return filtered_documents


# NOTE(fmontei): No need to include `@require_revision_exists` decorator as
# the this function immediately calls `revision_documents_get` for both
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
    docs = (revision_documents_get(revision_id,
                                   include_history=True,
                                   unique_only=False)
            if revision_id != 0 else [])
    comparison_docs = (revision_documents_get(comparison_revision_id,
                                              include_history=True,
                                              unique_only=False)
                       if comparison_revision_id != 0 else [])

    # Remove each deleted document and its older counterparts because those
    # documents technically don't exist.
    for documents in (docs, comparison_docs):
        documents = _exclude_deleted_documents(documents)

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
        # Update the revision tag if it already exists.
        tag_to_update = session.query(models.RevisionTag)\
            .filter_by(tag=tag, revision_id=revision_id)\
            .one()
        tag_to_update.update({'data': data})
        tag_to_update.save(session=session)
        resp = tag_to_update.to_dict()

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
    query = raw_query(
        """DELETE FROM revision_tags WHERE tag=:tag AND
            revision_id=:revision_id;""", tag=tag, revision_id=revision_id)
    if query.rowcount == 0:
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


def revision_rollback(revision_id, latest_revision, session=None):
    """Rollback the latest revision to revision specified by ``revision_id``.

    Rolls back the latest revision to the revision specified by ``revision_id``
    thereby creating a new, carbon-copy revision.

    :param revision_id: Revision ID to which to rollback.
    :param latest_revision: Dictionary representation of the latest revision
        in the system.
    :returns: The newly created revision.
    """
    session = session or get_session()
    latest_revision_hashes = [
        (d['data_hash'], d['metadata_hash'])
        for d in latest_revision['documents']]

    if latest_revision['id'] == revision_id:
        LOG.debug('The revision being rolled back to is the current revision.'
                  'Expect no meaningful changes.')

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

    # No changes have been made between the target revision to rollback to
    # and the latest revision.
    if set(doc_diff.values()) == set([False]):
        LOG.debug('The revision being rolled back to has the same documents '
                  'as that of the current revision. Expect no meaningful '
                  'changes.')

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


####################


@require_revision_exists
def validation_create(revision_id, val_name, val_data, session=None):
    session = session or get_session()

    validation_kwargs = {
        'revision_id': revision_id,
        'name': val_name,
        'status': val_data.get('status', None),
        'validator': val_data.get('validator', None),
        'errors': val_data.get('errors', []),
    }

    validation = models.Validation()

    with session.begin():
        validation.update(validation_kwargs)
        validation.save(session=session)

    return validation.to_dict()


@require_revision_exists
def validation_get_all(revision_id, session=None):
    # Query selects only unique combinations of (name, status) from the
    # `Validations` table and prioritizes 'failure' result over 'success'
    # result via alphabetical ordering of the status column. Each document
    # has its own validation but for this query we want to return the result
    # of the overall validation for the revision. If just 1 document failed
    # validation, we regard the validation for the whole revision as 'failure'.

    query = raw_query("""
        SELECT DISTINCT name, status FROM validations as v1
            WHERE revision_id=:revision_id AND status = (
                SELECT status FROM validations as v2
                    WHERE v2.name = v1.name
                    ORDER BY status
                    LIMIT 1
            )
            GROUP BY name, status
            ORDER BY name, status;
    """, revision_id=revision_id)

    result = query.fetchall()
    return result


@require_revision_exists
def validation_get_all_entries(revision_id, val_name, session=None):
    session = session or get_session()

    entries = session.query(models.Validation)\
        .filter_by(**{'revision_id': revision_id, 'name': val_name})\
        .order_by(models.Validation.created_at.asc())\
        .all()

    return [e.to_dict() for e in entries]


@require_revision_exists
def validation_get_entry(revision_id, val_name, entry_id, session=None):
    session = session or get_session()
    entries = validation_get_all_entries(
        revision_id, val_name, session=session)
    try:
        return entries[entry_id]
    except IndexError:
        raise errors.ValidationNotFound(
            revision_id=revision_id, validation_name=val_name,
            entry_id=entry_id)
