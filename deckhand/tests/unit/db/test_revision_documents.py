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

from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestRevisionDocumentsFiltering(base.TestDbBase):

    def test_document_filtering_by_bucket_name(self):
        document = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, document)

        revision_id = self.create_documents(bucket_name, [])[0]['revision_id']

        filters = {'bucket_name': bucket_name}
        retrieved_documents = self.list_revision_documents(
            revision_id, **filters)

        self.assertEqual(1, len(retrieved_documents))
        self.assertEqual(bucket_name, retrieved_documents[0]['bucket_name'])

    def test_document_filtering_exclude_deleted_documents(self):
        documents = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, documents)

        revision_id = self.create_documents(bucket_name, [])[0]['revision_id']
        retrieved_documents = self.list_revision_documents(
            revision_id, include_history=False, deleted=False)

        self.assertEmpty(retrieved_documents)

    def test_revision_document_filtering_with_single_item_list(self):
        document = base.DocumentFixture.get_minimal_fixture()
        # If not provided, Deckhand defaults to 'cleartext'.
        document['metadata']['storagePolicy'] = None
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, document)

        retrieved_documents = self.list_revision_documents(
            created_documents[0]['revision_id'],
            **{'metadata.storagePolicy': ['cleartext']})
        self.assertEqual([d['id'] for d in created_documents],
                         [d['id'] for d in retrieved_documents])

    def test_revision_document_filtering_with_multi_item_list(self):
        all_created_documents = []

        for storage_policy in ['cleartext', 'cleartext']:
            document = base.DocumentFixture.get_minimal_fixture()
            document['metadata']['storagePolicy'] = storage_policy
            bucket_name = test_utils.rand_name('bucket')
            created_documents = self.create_documents(bucket_name, document)
            all_created_documents.extend(created_documents)

            retrieved_documents = self.list_revision_documents(
                created_documents[0]['revision_id'],
                **{'metadata.storagePolicy': ['cleartext', 'encrypted']})

            self.assertEqual([d['id'] for d in all_created_documents],
                             [d['id'] for d in retrieved_documents])

    def test_revision_document_filtering_single_item_list_exclude_all(self):
        documents = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        # If not provided, Deckhand defaults to 'cleartext'.
        for document in documents:
            document['metadata']['storagePolicy'] = None
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, documents)

        retrieved_documents = self.list_revision_documents(
            created_documents[0]['revision_id'],
            **{'metadata.storagePolicy': ['encrypted']})
        self.assertEmpty(retrieved_documents)

    def test_revision_document_filtering_single_item_list_exclude_many(self):
        documents = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        # Only the first document should be returned.
        documents[0]['metadata']['storagePolicy'] = 'encrypted'
        for document in documents[1:]:
            document['metadata']['storagePolicy'] = 'cleartext'
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, documents)

        retrieved_documents = self.list_revision_documents(
            created_documents[0]['revision_id'],
            **{'metadata.storagePolicy': ['encrypted']})
        self.assertEqual([created_documents[0]['id']],
                         [d['id'] for d in retrieved_documents])

    def test_revision_document_filtering_with_multi_item_list_exclude(self):
        for storage_policy in ['cleartext', 'cleartext']:
            document = base.DocumentFixture.get_minimal_fixture()
            document['metadata']['storagePolicy'] = storage_policy
            bucket_name = test_utils.rand_name('bucket')
            created_documents = self.create_documents(bucket_name, document)

            retrieved_documents = self.list_revision_documents(
                created_documents[0]['revision_id'],
                **{'metadata.storagePolicy': ['wrong_val', 'encrypted']})

            self.assertEmpty(retrieved_documents)
