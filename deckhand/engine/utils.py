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

import collections

from deckhand.common import utils


def deep_merge(dct, merge_dct):
    """Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, deep_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``, except for merge conflicts, which are resolved by prioritizing
    the ``dct`` value.

    Borrowed from: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9#file-deep_merge-py # noqa

    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict) and
                isinstance(merge_dct[k], collections.Mapping)):
            deep_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def deep_delete(target, value, parent):
    """Recursively search for then delete ``target`` from ``parent``.

    :param target: Target value to remove.
    :param value: Current value in a list or dict to compare against
        ``target`` and removed from ``parent`` given match.
    :param parent: Tracks the parent data structure from which ``value``
        is removed.
    :type parent: list or dict
    :returns: Whether ``target`` was found.
    :rtype: bool
    """

    if value == target:
        if isinstance(parent, list):
            parent.remove(value)
            return True
        elif isinstance(parent, dict):
            for k, v in parent.items():
                if v == value:
                    parent.pop(k)
                    return True
    elif isinstance(value, list):
        for v in value:
            found = deep_delete(target, v, value)
            if found:
                return True
    elif isinstance(value, dict):
        for v in value.values():
            found = deep_delete(target, v, value)
            if found:
                return True
    return False


def deep_scrub(value, parent):
    """Scrubs all primitives in document data recursively. Useful for scrubbing
    any and all secret data that may have been substituted into the document
    data section before logging it out safely following an error.
    """
    primitive = (int, float, complex, str, bytes, bool)

    def is_primitive(value):
        return isinstance(value, primitive)

    if is_primitive(value):
        if isinstance(parent, list):
            parent[parent.index(value)] = 'Scrubbed'
        elif isinstance(parent, dict):
            for k, v in parent.items():
                if v == value:
                    parent[k] = 'Scrubbed'
    elif isinstance(value, list):
        for v in value:
            deep_scrub(v, value)
    elif isinstance(value, dict):
        for v in value.values():
            deep_scrub(v, value)


def exclude_deleted_documents(documents):
    """Excludes all documents that have been deleted including all documents
    earlier in the revision history with the same ``metadata.name`` and
    ``schema`` from ``documents``.
    """
    documents_map = {}  # (document.meta) => should be included?

    for doc in sorted(documents, key=lambda x: x['created_at']):
        if doc['deleted'] is True:
            previous_doc = documents_map.get(meta(doc))
            if previous_doc:
                if doc['deleted_at'] >= previous_doc['created_at']:
                    documents_map[meta(doc)] = None
        else:
            documents_map[meta(doc)] = doc
    return [d for d in documents_map.values() if d is not None]


def filter_revision_documents(documents, unique_only, **filters):
    """Return the list of documents that match filters.

    :param documents: List of documents to apply ``filters`` to.
    :param unique_only: Return only unique documents if ``True``.
    :param filters: Dictionary attributes (including nested) used to filter
        out revision documents.
    :returns: List of documents that match specified filters.
    """
    filtered_documents = {}
    unique_filters = ('schema', 'name', 'layer')
    exclude_deleted = filters.pop('deleted', None) is False

    if exclude_deleted:
        documents = exclude_deleted_documents(documents)

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


def meta(document):
    return (
        document['schema'],
        document['metadata'].get('layeringDefinition', {}).get('layer'),
        document['metadata'].get('name')
    )
