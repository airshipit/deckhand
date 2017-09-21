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
        # Edge case for when all documents are deleted from a bucket. Still
        # need to return bucket_id and revision_id.
        if len(documents) == 1 and documents[0]['deleted']:
            resp_obj = {'status': {}}
            resp_obj['status']['bucket'] = documents[0]['bucket_name']
            resp_obj['status']['revision'] = documents[0]['revision_id']
            return [resp_obj]

        resp_list = []
        attrs = ['id', 'metadata', 'data', 'schema']

        for document in documents:
            resp_obj = {x: document[x] for x in attrs}
            resp_obj.setdefault('status', {})
            resp_obj['status']['bucket'] = document['bucket_name']
            resp_obj['status']['revision'] = document['revision_id']
            resp_list.append(resp_obj)

        # In the case where no documents are passed to PUT
        # buckets/{{bucket_name}}/documents, we need to mangle the response
        # body a bit. The revision_id and buckete_id should be returned, as
        # at the very least the revision_id will be needed by the user.
        if not resp_list and documents:
            resp_obj = {}
            resp_obj.setdefault('status', {})
            resp_obj['status']['bucket'] = documents[0]['bucket_id']
            resp_obj['status']['revision'] = documents[0]['revision_id']

            resp_list.append(resp_obj)

        return resp_list
