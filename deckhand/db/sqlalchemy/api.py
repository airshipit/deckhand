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
import six

from oslo_config import cfg
from oslo_db import exception as db_exception
from oslo_db import options
from oslo_db.sqlalchemy import session
from oslo_log import log as logging
from oslo_serialization import jsonutils as json
import sqlalchemy.orm as sa_orm
from sqlalchemy import text

from deckhand.common import utils
from deckhand.db.sqlalchemy import models
from deckhand.engine import utils as eng_utils
from deckhand import errors
from deckhand import types

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

options.set_defaults(CONF)

_FACADE = None
_LOCK = threading.Lock()


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


def drop_db():
    models.unregister_models(get_engine())


def setup_db(connection_string, create_tables=False):
    models.register_models(get_engine(), connection_string)
    if create_tables:
        models.create_tables(get_engine())


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
            existing_document_names = [
                eng_utils.meta(x) for x in existing_documents
            ]
            conflicting_names = [
                eng_utils.meta(x) for x in documents
                if eng_utils.meta(x) not in existing_document_names and
                x['schema'].startswith(schema)
            ]
            if existing_document_names and conflicting_names:
                raise errors.SingletonDocumentConflict(
                    schema=existing_document_names[0][0],
                    layer=existing_document_names[0][1],
                    name=existing_document_names[0][2],
                    conflict=', '.join(["[%s, %s] %s" % (x[0], x[1], x[2])
                                       for x in conflicting_names]))
            return f(bucket_name, documents, *args, **kwargs)
        return wrapper
    return decorator


@require_unique_document_schema(types.LAYERING_POLICY_SCHEMA)
def documents_create(bucket_name, documents, session=None):
    """Create a set of documents and associated bucket.

    If no changes are detected, a new revision will not be created. This
    allows services to periodically re-register their schemas without
    creating unnecessary revisions.

    :param bucket_name: The name of the bucket with which to associate created
        documents.
    :param documents: List of documents to be created.
    :param session: Database session object.
    :returns: List of created documents in dictionary format.
    :raises DocumentExists: If the document already exists in the DB for any
        bucket.
    """
    session = session or get_session()
    resp = []

    with session.begin():
        documents_to_create = _documents_create(bucket_name, documents,
                                                session=session)

        # The documents to be deleted are computed by comparing the documents
        # for the previous revision (if it exists) that belong to `bucket_name`
        # with `documents`: the difference between the former and the latter.
        document_history = [
            d for d in revision_documents_get(bucket_name=bucket_name,
                                              session=session)
        ]
        documents_to_delete = [
            h for h in document_history if eng_utils.meta(h) not in [
                eng_utils.meta(d) for d in documents]
        ]

        # Only create a revision if any docs have been created, changed or
        # deleted.
        if any([documents_to_create, documents_to_delete]):
            revision = revision_create(session=session)
            bucket = bucket_get_or_create(bucket_name, session=session)

        if documents_to_delete:
            LOG.debug('Deleting documents: %s.',
                      [eng_utils.meta(d) for d in documents_to_delete])
            deleted_documents = []

            for d in documents_to_delete:
                doc = document_delete(d, revision['id'], bucket,
                                      session=session)

                deleted_documents.append(doc)
                resp.append(doc)

        if documents_to_create:
            LOG.debug(
                'Creating documents: %s.', [
                    (d['schema'], d['layer'], d['name'])
                    for d in documents_to_create
                ]
            )
            for doc in documents_to_create:
                doc['bucket_id'] = bucket['id']
                doc['revision_id'] = revision['id']
                if not doc.get('orig_revision_id'):
                    doc['orig_revision_id'] = doc['revision_id']

                try:
                    doc.save(session=session)
                except db_exception.DBDuplicateEntry:
                    raise errors.DuplicateDocumentExists(
                        schema=doc['schema'], layer=doc['layer'],
                        name=doc['name'], bucket=bucket['name'])

                resp.append(doc.to_dict())
    # NOTE(fmontei): The orig_revision_id is not copied into the
    # revision_id for each created document, because the revision_id here
    # should reference the just-created revision. In case the user needs
    # the original revision_id, that is returned as well.

    return resp


def document_delete(document, revision_id, bucket, session=None):
    """Delete a document

    Creates a new document with the bare minimum information about the document
    that is to be deleted, and then sets the appropriate deleted fields

    :param document: document object/dict to be deleted
    :param revision_id: id of the revision where the document is to be deleted
    :param bucket: bucket object/dict where the document will be deleted from
    :param session: Database session object.
    :return: dict representation of deleted document
    """
    session = session or get_session()

    doc = models.Document()
    # Store bare minimum information about the document.
    doc['schema'] = document['schema']
    doc['name'] = document['name']
    doc['layer'] = document['layer']
    doc['data'] = {}
    doc['meta'] = document['metadata']
    doc['data_hash'] = _make_hash({})
    doc['metadata_hash'] = _make_hash({})
    doc['bucket_id'] = bucket['id']
    doc['revision_id'] = revision_id

    # Save and mark the document as `deleted` in the database.
    try:
        doc.save(session=session)
    except db_exception.DBDuplicateEntry:
        raise errors.DuplicateDocumentExists(
            schema=doc['schema'], layer=doc['layer'],
            name=doc['name'], bucket=bucket['name'])
    doc.safe_delete(session=session)

    return doc.to_dict()


def documents_delete_from_buckets_list(bucket_names, session=None):
    """Delete all documents in the provided list of buckets

    :param bucket_names: list of bucket names for which the associated
        buckets and their documents need to be deleted.
    :param session: Database session object.
    :returns: A new model.Revisions object after all the documents have been
        deleted.
    """
    session = session or get_session()

    with session.begin():
        # Create a new revision
        revision = models.Revision()
        revision.save(session=session)

        for bucket_name in bucket_names:

            documents_to_delete = [
                d for d in revision_documents_get(bucket_name=bucket_name,
                                                  session=session)
                if "deleted" not in d or not d['deleted']
            ]

            bucket = bucket_get_or_create(bucket_name, session=session)

            if documents_to_delete:
                LOG.debug('Deleting documents: %s.',
                          [eng_utils.meta(d) for d in documents_to_delete])

                for document in documents_to_delete:
                    document_delete(document, revision['id'], bucket,
                                    session=session)

    return revision


def _documents_create(bucket_name, documents, session=None):
    documents = copy.deepcopy(documents)
    session = session or get_session()
    filters = ('name', 'schema', 'layer')
    changed_documents = []

    def _document_create(document):
        model = models.Document()
        model.update(document)
        return model

    for document in documents:
        document.setdefault('data', {})
        document = _fill_in_metadata_defaults(document)

        # Hash the document's metadata and data to later  efficiently check
        # whether those data have changed.
        document['data_hash'] = _make_hash(document['data'])
        document['metadata_hash'] = _make_hash(document['meta'])

        try:
            existing_document = document_get(
                raw_dict=True, deleted=False, revision_id='latest',
                **{x: document[x] for x in filters})
        except errors.DocumentNotFound:
            # Ignore bad data at this point. Allow creation to bubble up the
            # error related to bad data.
            existing_document = None

        if existing_document:
            # If the document already exists in another bucket, raise an error.
            if existing_document['bucket_name'] != bucket_name:
                raise errors.DuplicateDocumentExists(
                    schema=existing_document['schema'],
                    name=existing_document['name'],
                    layer=existing_document['layer'],
                    bucket=existing_document['bucket_name'])

            # By this point we know existing_document and document have the
            # same name, schema and layer due to the filters passed to the DB
            # query. But still want to check whether the document is precisely
            # the same one by comparing metadata/data hashes.
            if (existing_document['data_hash'] == document['data_hash'] and
                existing_document['metadata_hash'] == document[
                    'metadata_hash']):
                # Since the document has not changed, reference the original
                # revision in which it was created. This is necessary so that
                # the correct revision history is maintained.
                if existing_document['orig_revision_id']:
                    document['orig_revision_id'] = existing_document[
                        'orig_revision_id']
                else:
                    document['orig_revision_id'] = existing_document[
                        'revision_id']

    # Create all documents, even unchanged ones, for the current revision. This
    # makes the generation of the revision diff a lot easier.
    for document in documents:
        doc = _document_create(document)
        changed_documents.append(doc)

    return changed_documents


def _fill_in_metadata_defaults(document):
    document['meta'] = document.pop('metadata')
    document['name'] = document['meta']['name']

    if not document['meta'].get('storagePolicy', None):
        document['meta']['storagePolicy'] = 'cleartext'

    document['meta'].setdefault('layeringDefinition', {})
    document['layer'] = document['meta']['layeringDefinition'].get('layer')

    if 'abstract' not in document['meta']['layeringDefinition']:
        document['meta']['layeringDefinition']['abstract'] = False

    if 'replacement' not in document['meta']:
        document['meta']['replacement'] = False

    return document


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

    # Documents with the same metadata.name and schema can exist across
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
    raise errors.DocumentNotFound(filters=filters)


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
        bucket.update({'name': bucket_name})
        bucket.save(session=session)

    return bucket.to_dict()


####################

def bucket_get_all(session=None, **filters):
    """Return list of all buckets.

    :param session: Database session object.
    :returns: List of dictionary representations of retrieved buckets.
    """
    session = session or get_session()

    buckets = session.query(models.Bucket)\
        .all()
    result = []
    for bucket in buckets:
        revision_dict = bucket.to_dict()
        if utils.deepfilter(revision_dict, **filters):
            result.append(bucket)

    return result


def revision_create(session=None):
    """Create a revision.

    :param session: Database session object.
    :returns: Dictionary representation of created revision.
    """
    session = session or get_session()

    revision = models.Revision()
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
        raise errors.RevisionNotFound(revision_id=revision_id)

    revision['documents'] = _update_revision_history(revision['documents'])

    return revision


def revision_get_latest(session=None):
    """Return the latest revision.

    :param session: Database session object.
    :returns: Dictionary representation of latest revision.
    """
    session = session or get_session()

    latest_revision = session.query(models.Revision)\
        .order_by(models.Revision.created_at.desc())\
        .first()

    if latest_revision:
        latest_revision = latest_revision.to_dict()
        latest_revision['documents'] = _update_revision_history(
            latest_revision['documents'])
    else:
        # If the latest revision doesn't exist, assume an empty revision
        # history and return a dummy revision instead for the purposes of
        # revision rollback.
        latest_revision = {'documents': [], 'id': 0}

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


@require_revision_exists
def revision_documents_get(revision_id=None, include_history=True,
                           unique_only=True, session=None, **filters):
    """Return the documents that match filters for the specified `revision_id`.

    :param revision_id: The ID corresponding to the ``Revision`` object. If the
        ID is ``None``, then retrieve the latest revision, if one exists.
    :param include_history: Return all documents for revision history prior
        and up to current revision, if ``True``. Default is ``True``.
    :param unique_only: Return only unique documents if ``True``. Default is
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
        raise errors.RevisionNotFound(revision_id=revision_id)

    revision_documents = _update_revision_history(revision_documents)

    filtered_documents = eng_utils.filter_revision_documents(
        revision_documents, unique_only, **filters)

    return filtered_documents


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

    if data is None:
        data = {}

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
        LOG.debug('Tag %s already exists for revision_id %s. Attempting to '
                  'update the entry.', tag, revision_id)
        try:
            tag_to_update = session.query(models.RevisionTag)\
                .filter_by(tag=tag, revision_id=revision_id)\
                .one()
        except sa_orm.exc.NoResultFound:
            raise errors.RevisionTagNotFound(tag=tag, revision=revision_id)
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
    latest_revision_docs = revision_documents_get(latest_revision['id'],
                                                  session=session)
    latest_revision_hashes = [
        (d['data_hash'], d['metadata_hash']) for d in latest_revision_docs
    ]

    if latest_revision['id'] == revision_id:
        LOG.debug('The revision being rolled back to is the current revision.'
                  'Expect no meaningful changes.')

    if revision_id == 0:
        # Delete all existing documents in all buckets
        all_buckets = bucket_get_all(deleted=False)
        bucket_names = [six.text_type(b['name']) for b in all_buckets]
        revision = documents_delete_from_buckets_list(bucket_names,
                                                      session=session)

        return revision.to_dict()
    else:
        # Sorting the documents so the documents in the new revision are in
        # the same order as the previous revision to support stable testing
        orig_revision_docs = sorted(revision_documents_get(revision_id,
                                                           session=session),
                                    key=lambda d: d['id'])

    # A mechanism for determining whether a particular document has changed
    # between revisions. Keyed with the document_id, the value is True if
    # it has changed, else False.
    doc_diff = {}
    # List of unique buckets that exist in this revision
    unique_buckets = []
    for orig_doc in orig_revision_docs:
        if ((orig_doc['data_hash'], orig_doc['metadata_hash'])
                not in latest_revision_hashes):
            doc_diff[orig_doc['id']] = True
        else:
            doc_diff[orig_doc['id']] = False
        if orig_doc['bucket_id'] not in unique_buckets:
            unique_buckets.append(orig_doc['bucket_id'])

    # We need to find which buckets did not exist at this revision
    buckets_to_delete = []
    all_buckets = bucket_get_all(deleted=False)
    for bucket in all_buckets:
        if bucket['id'] not in unique_buckets:
            buckets_to_delete.append(six.text_type(bucket['name']))

    # Create the new revision,
    if len(buckets_to_delete) > 0:
        new_revision = documents_delete_from_buckets_list(buckets_to_delete,
                                                          session=session)
    else:
        new_revision = models.Revision()
        with session.begin():
            new_revision.save(session=session)

    # No changes have been made between the target revision to rollback to
    # and the latest revision.
    if set(doc_diff.values()) == set([False]):
        LOG.debug('The revision being rolled back to has the same documents '
                  'as that of the current revision. Expect no meaningful '
                  'changes.')

    # Create the documents for the revision.
    for orig_document in orig_revision_docs:
        orig_document['revision_id'] = new_revision['id']
        orig_document['meta'] = orig_document.pop('metadata')

        new_document = models.Document()
        new_document.update({x: orig_document[x] for x in (
            'name', 'meta', 'layer', 'data', 'data_hash', 'metadata_hash',
            'schema', 'bucket_id')})
        new_document['revision_id'] = new_revision['id']

        # If the document has changed, then use the revision_id of the new
        # revision, otherwise use the original revision_id to preserve the
        # revision history.
        if doc_diff[orig_document['id']]:
            new_document['orig_revision_id'] = new_revision['id']
        else:
            new_document['orig_revision_id'] = revision_id

        with session.begin():
            new_document.save(session=session)

    new_revision = new_revision.to_dict()
    new_revision['documents'] = _update_revision_history(
        new_revision['documents'])

    return new_revision


####################


def _get_validation_policies_for_revision(revision_id, session=None):
    session = session or get_session()

    # Check if a ValidationPolicy for the revision exists.
    validation_policies = document_get_all(
        session, revision_id=revision_id, deleted=False,
        schema=types.VALIDATION_POLICY_SCHEMA)
    if not validation_policies:
        # Otherwise return early.
        LOG.debug('Failed to find a ValidationPolicy for revision ID %s. '
                  'Only the "%s" results will be included in the response.',
                  revision_id, types.DECKHAND_SCHEMA_VALIDATION)
        validation_policies = []

    return validation_policies


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
    session = session or get_session()

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

    result = {v[0]: v for v in query.fetchall()}
    actual_validations = set(v[0] for v in result.values())

    validation_policies = _get_validation_policies_for_revision(revision_id)
    if not validation_policies:
        return result.values()

    # TODO(fmontei): Raise error for expiresAfter conflicts for duplicate
    # validations across ValidationPolicy documents.
    expected_validations = set()
    for vp in validation_policies:
        expected_validations = expected_validations.union(
            list(v['name'] for v in vp['data'].get('validations', [])))

    missing_validations = expected_validations - actual_validations
    extra_validations = actual_validations - expected_validations

    # If an entry in the ValidationPolicy was never POSTed, set its status
    # to failure.
    for missing_validation in missing_validations:
        result[missing_validation] = (missing_validation, 'failure')

    # If an entry is not in the ValidationPolicy but was externally registered,
    # then override its status to "ignored [{original_status}]".
    for extra_validation in extra_validations:
        result[extra_validation] = (
            extra_validation, 'ignored [%s]' % result[extra_validation][1])

    return result.values()


def _check_validation_entries_against_validation_policies(
        revision_id, entries, val_name=None, session=None):
    session = session or get_session()

    result = [e.to_dict() for e in entries]
    result_map = {}
    for r in result:
        result_map.setdefault(r['name'], [])
        result_map[r['name']].append(r)
    actual_validations = set(v['name'] for v in result)

    validation_policies = _get_validation_policies_for_revision(revision_id)
    if not validation_policies:
        return result

    # TODO(fmontei): Raise error for expiresAfter conflicts for duplicate
    # validations across ValidationPolicy documents.
    expected_validations = set()
    for vp in validation_policies:
        expected_validations |= set(
            v['name'] for v in vp['data'].get('validations', []))

    missing_validations = expected_validations - actual_validations
    extra_validations = actual_validations - expected_validations

    # If an entry in the ValidationPolicy was never POSTed, set its status
    # to failure.
    for missing_name in missing_validations:
        if val_name is None or missing_name == val_name:
            result.append({
                'id': len(result),
                'name': val_name,
                'status': 'failure',
                'errors': [{
                    'message': 'The result for this validation was never '
                               'externally registered so its status defaulted '
                               'to "failure".'
                }]
            })
            break

    # If an entry is not in the ValidationPolicy but was externally registered,
    # then override its status to "ignored [{original_status}]".
    for extra_name in extra_validations:
        for entry in result_map[extra_name]:
            original_status = entry['status']
            entry['status'] = 'ignored [%s]' % original_status
            entry.setdefault('errors', [])

            msg_args = eng_utils.meta(vp) + (
                ', '.join(v['name'] for v in vp['data'].get(
                    'validations', [])),
            )
            for vp in validation_policies:
                entry['errors'].append({
                    'message': (
                        'The result for this validation was externally '
                        'registered but has been ignored because it is not '
                        'found in the validations for ValidationPolicy '
                        '[%s, %s] %s: %s.' % msg_args
                    )
                })

    return result


@require_revision_exists
def validation_get_all_entries(revision_id, val_name=None, session=None):
    session = session or get_session()

    entries = session.query(models.Validation)\
        .filter_by(revision_id=revision_id)
    if val_name:
        entries = entries.filter_by(name=val_name)
    entries.order_by(models.Validation.created_at.asc())\
        .all()

    return _check_validation_entries_against_validation_policies(
        revision_id, entries, val_name=val_name, session=session)


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
