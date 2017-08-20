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


class TestDocuments(base.TestDbBase):

    def test_create_and_show_bucket(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(1, len(documents))

        retrieved_document = self.show_document(id=documents[0]['id'])
        self.assertEqual(documents[0], retrieved_document)

    def test_create_document_conflict(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, payload)
        documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(documents, list)
        self.assertEmpty(documents)

    def test_create_document_and_show_revision(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(1, len(documents))

        for document in documents:
            revision = self.show_revision(document['revision_id'])
            self.validate_revision(revision)
            self.assertEqual(document['revision_id'], revision['id'])

    def test_list_documents_by_revision_id(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        revision = self.show_revision(documents[0]['revision_id'])
        self.assertEqual(1, len(revision['documents']))
        self.assertEqual(documents[0], revision['documents'][0])

    def test_list_multiple_documents_by_revision_id(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(3, len(documents))

        for document in documents:
            revision = self.show_revision(document['revision_id'])
            self.validate_revision(revision)
            self.assertEqual(document['revision_id'], revision['id'])

    def test_list_documents_by_revision_id_and_filters(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        document = self.create_documents(bucket_name, payload)[0]
        filters = {
            'schema': document['schema'],
            'metadata.name': document['metadata']['name'],
            'metadata.layeringDefinition.abstract':
                document['metadata']['layeringDefinition']['abstract'],
            'metadata.layeringDefinition.layer':
                document['metadata']['layeringDefinition']['layer'],
            'metadata.label': document['metadata']['label']
        }

        documents = self.list_revision_documents(
            document['revision_id'], **filters)
        self.assertEqual(1, len(documents))
        self.assertEqual(document, documents[0])
