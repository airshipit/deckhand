# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from deepdiff import DeepDiff
from deepdiff.helper import RemapDict
import jsonpickle

from deckhand.control import common
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import utils
from deckhand import errors


def revision_diff(revision_id, comparison_revision_id, deepdiff=False):
    """Generate the diff between two revisions.

    Generate the diff between the two revisions: `revision_id` and
    `comparison_revision_id`.
    a. When deepdiff=False: A basic comparison of the revisions in terms of
    how the buckets involved have changed is generated. Only buckets with
    existing documents in either of the two revisions in question will be
    reported.
    b. When deepdiff=True: Along with basic comparision, It will generate deep
    diff between revisions' modified buckets.

    Only in case of diff, The ordering of the two revision IDs is
    interchangeable, i.e. no matter the order, the same result is generated.

    The differences include:

        - "created": A bucket has been created between the revisions.
        - "deleted": A bucket has been deleted between the revisions.
        - "modified": A bucket has been modified between the revisions.
                      When deepdiff is enabled, It also includes deep
                      difference between the revisions.
        - "unmodified": A bucket remains unmodified between the revisions.

    :param revision_id: ID of the first revision.
    :param comparison_revision_id: ID of the second revision.
    :param deepdiff: Whether deepdiff needed or not.
    :returns: A dictionary, keyed with the bucket IDs, containing any of the
        differences enumerated above.

    Examples Diff::

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

    Examples DeepDiff::

        # GET /api/v1.0/revisions/3/deepdiff/4
        bucket_a: modified
        bucket_a diff:
          document_changed:
            count: 1
            details:
              ('example/Kind/v1', 'doc-b'):
                data_changed:
                  values_changed:
                    root['foo']: {new_value: 3, old_value: 2}
                metadata_changed: {}

        # GET /api/v1.0/revisions/2/deepdiff/3
        bucket_a: modified
        bucket_a diff:
          document_added:
            count: 1
            details:
            - [example/Kind/v1, doc-c]

        # GET /api/v1.0/revisions/0/deepdiff/0
        {}

        # GET /api/v1.0/revisions/0/deepdiff/3
        bucket_a: created
    """
    if deepdiff:
        docs = (_render_documents(revision_id) if revision_id != 0 else [])
        comparison_docs = (_render_documents(comparison_revision_id)
                           if comparison_revision_id != 0 else [])
    else:
        # Retrieve document history for each revision. Since `revision_id` of 0
        # doesn't exist, treat it as a special case: empty list.
        docs = (db_api.revision_documents_get(revision_id,
                                              include_history=True,
                                              unique_only=False)
                if revision_id != 0 else [])
        comparison_docs = (db_api.revision_documents_get(
                           comparison_revision_id,
                           include_history=True,
                           unique_only=False
                           ) if comparison_revision_id != 0 else [])

    # Remove each deleted document and its older counterparts because those
    # documents technically don't exist.
    docs = utils.exclude_deleted_documents(docs)
    comparison_docs = utils.exclude_deleted_documents(comparison_docs)

    revision = db_api.revision_get(revision_id) if revision_id != 0 else None
    comparison_revision = (db_api.revision_get(comparison_revision_id)
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
    # and `comparison_revision_id` -- i.e. their union.
    unshared_buckets = set(buckets.keys()).union(
        comparison_buckets.keys()) - shared_buckets

    result = {}

    def _compare_buckets(b1, b2):
        # Checks whether buckets' documents are identical.
        return (sorted([(d['data_hash'], d['metadata_hash']) for d in b1]) ==
                sorted([(d['data_hash'], d['metadata_hash']) for d in b2]))

    # If the list of documents for each bucket is identical, then the result
    # is "unmodified", else "modified".
    for bucket_name in shared_buckets:
        unmodified = _compare_buckets(buckets[bucket_name],
                                      comparison_buckets[bucket_name])
        if unmodified:
            result[bucket_name] = 'unmodified'
        else:
            result[bucket_name] = 'modified'
            # If deepdiff is enabled, find out diff between buckets
            if deepdiff:
                bucket_diff = _diff_buckets(buckets[bucket_name],
                                            comparison_buckets[bucket_name])
                result[bucket_name + ' diff'] = bucket_diff

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


def _diff_buckets(b1, b2):
    """Function to provide deep diff between two revisions"""
    b1_tmp = {}
    b2_tmp = {}
    change_count = 0
    change_details = {}
    diff_result = {}
    alias = lambda d: (d['schema'], d['name'])

    b1_tmp.update({
        alias(d): d
        for d in b1
    })
    b2_tmp.update({
        alias(d): d
        for d in b2
    })

    # doc deleted
    doc_deleted = list(set(b1_tmp.keys()) - set(b2_tmp.keys()))
    # new doc added
    doc_added = list(set(b2_tmp.keys()) - set(b1_tmp.keys()))

    if len(doc_added) > 0:
        diff_result.update({'document_added': {
            'count': len(doc_added),
            'details': doc_added}})
    if len(doc_deleted) > 0:
        diff_result.update({'document_deleted': {
            'count': len(doc_deleted),
            'details': doc_deleted}})

    # find modified documents
    for k, d in b1_tmp.items():
        if k in b2_tmp:
            # matched document, lets see changes
            if (d['data_hash'], d['metadata_hash']) != (
               b2_tmp[k]['data_hash'], b2_tmp[k]['metadata_hash']):
                # document change counter
                change_count += 1

                data_changed = {'encrypted': True}
                # if document is not encrypted then show diff else hide diff
                # data.
                if not b2_tmp[k].is_encrypted:
                    try:
                        # deepdiff returns deepdiff object. So first
                        # serializing to json then deserializing
                        # to dict.
                        data_changed = jsonpickle.decode(
                            DeepDiff(d['data'], b2_tmp[k]['data']).json)
                    # deepdiff doesn't provide custom exceptions;
                    # have to use Exception.
                    except Exception as ex:
                        raise errors.DeepDiffException(details=str(ex))
                try:
                    metadata_changed = jsonpickle.decode(
                        DeepDiff(d['metadata'],
                                 b2_tmp[k]['metadata']).json)
                except Exception as ex:
                        raise errors.DeepDiffException(details=str(ex))

                change_details.update({
                    str(k): {'data_changed': data_changed,
                             'metadata_changed': metadata_changed}})

    if change_count > 0:
        diff_result.update({'document_changed': {
            'count': change_count,
            'details': change_details
        }})
    # yaml_safedump failed to parse python objects;
    # need diff result format before pass it yaml_safedump
    return _format_diff_result(diff_result)


def _format_diff_result(dr):
    """Formats diff result per yaml_safedump parsing."""
    if isinstance(dr, dict):
        for k, v in dr.items():
            if isinstance(v, RemapDict):
                v = dict(v)
                dr.update({k: v})
            if isinstance(v, type):
                dr.update({k: str(v)})
            if isinstance(v, dict):
                _format_diff_result(v)
    return dr


def _render_documents(revision_id):
    """Provides rendered document by given revision id."""
    filters = {'deleted': False}
    rendered_documents, _ = common.get_rendered_docs(revision_id, **filters)
    return rendered_documents
