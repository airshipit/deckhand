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

from deckhand.control import common
from deckhand import types


class ViewBuilder(common.ViewBuilder):
    """Model document API responses as a python dictionary.

    There are 2 cases for rendering the response body below.

    1. Treat the case where all documents in a bucket have been deleted as a
    special case. The response body must still include the revision_id and
    bucket_id. It is not meaningful to include other data about the deleted
    documents as technically they don't exist.
    2. Add all non-deleted documents to the response body.
    """

    _collection_name = 'documents'

    def list(self, documents):
        resp_list = []
        attrs = ['id', 'metadata', 'data', 'schema']

        for document in documents:
            if document['deleted']:
                continue
            if document['schema'].startswith(types.VALIDATION_POLICY_SCHEMA):
                continue
            resp_obj = {x: document[x] for x in attrs}
            resp_obj.setdefault('status', {})
            resp_obj['status']['bucket'] = document['bucket_name']
            resp_obj['status']['revision'] = document['revision_id']
            resp_list.append(resp_obj)

        # Edge case for when all documents are deleted from a bucket. To detect
        # the edge case, check whether ``resp_list`` is empty and whether there
        # are still documents to be returned. This means that all the documents
        # are either deleted or validation policies. Either way, we still need
        # to return bucket_id and revision_id, which should be the same
        # across all the documents in ``documents``.
        if not resp_list and documents:
            resp_obj = {'status': {}}
            resp_obj['status']['bucket'] = documents[0]['bucket_name']
            resp_obj['status']['revision'] = documents[0]['revision_id']
            return [resp_obj]

        return resp_list
