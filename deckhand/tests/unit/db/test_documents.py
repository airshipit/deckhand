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

from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestDocuments(base.TestDbBase):

    def setUp(self):
        super(TestDocuments, self).setUp()
        # Will create 3 documents: layering policy, plus a global and site
        # document.
        self.secrets_factory = factories.DocumentSecretFactory()
        self.documents_factory = factories.DocumentFactory(2, [1, 1])
        self.document_mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }

    def test_create_and_show_bucket(self):
        payload = self.documents_factory.gen_test(self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(3, len(documents))

        for idx in range(len(documents)):
            retrieved_document = self.show_document(id=documents[idx]['id'])
            self.assertIsNone(retrieved_document.pop('orig_revision_id'))
            self.assertEqual(documents[idx], retrieved_document)

    def test_create_and_get_multiple_document(self):
        payload = self.documents_factory.gen_test(
            self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(created_documents, list)
        self.assertEqual(3, len(created_documents))

    def test_list_documents_by_revision_id(self):
        payload = self.documents_factory.gen_test(
            self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        revision = self.show_revision(documents[0]['revision_id'])
        self.assertIsNone(revision['documents'][0].pop('orig_revision_id'))
        self.assertEqual(3, len(revision['documents']))
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
        payload = self.documents_factory.gen_test(
            self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        document = self.create_documents(bucket_name, payload)[1]

        filters = {
            'schema': document['schema'],
            'metadata.name': document['metadata']['name'],
            'metadata.layeringDefinition.abstract':
                document['metadata']['layeringDefinition']['abstract'],
            'metadata.layeringDefinition.layer':
                document['metadata']['layeringDefinition']['layer']
        }

        documents = self.list_revision_documents(
            document['revision_id'], **filters)

        self.assertEqual(1, len(documents))
        self.assertIsNone(documents[0].pop('orig_revision_id'))
        self.assertEqual(document, documents[0])

    def test_create_multiple_documents_and_get_revision(self):
        payload = self.documents_factory.gen_test(
            self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(created_documents, list)
        self.assertEqual(3, len(created_documents))

        # Validate that each document references the same revision.
        revisions = set(d['revision_id'] for d in created_documents)
        self.assertEqual(1, len(revisions))

        # Validate that the revision is valid.
        for document in created_documents:
            document['orig_revision_id'] = None
            revision = self.show_revision(document['revision_id'])
            self.assertEqual(3, len(revision['documents']))
            self.assertIn(document, revision['documents'])
            self.assertEqual(document['revision_id'], revision['id'])

    def test_get_documents_by_revision_id_and_filters(self):
        payload = self.documents_factory.gen_test(
            self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)

        for document in created_documents[1:]:
            filters = {
                'schema': document['schema'],
                'metadata.name': document['metadata']['name'],
                'metadata.layeringDefinition.abstract':
                    document['metadata']['layeringDefinition']['abstract'],
                'metadata.layeringDefinition.layer':
                    document['metadata']['layeringDefinition']['layer']
            }
            filtered_documents = self.list_revision_documents(
                document['revision_id'], **filters)

            self.assertEqual(1, len(filtered_documents))
            self.assertIsNone(filtered_documents[0].pop('orig_revision_id'))
            self.assertEqual(document, filtered_documents[0])

    def test_create_certificate(self):
        rand_secret = {'secret': test_utils.rand_password()}
        bucket_name = test_utils.rand_name('bucket')

        for storage_policy in ('encrypted', 'cleartext'):
            secret_doc_payload = self.secrets_factory.gen_test(
                'Certificate', storage_policy, rand_secret)
            created_documents = self.create_documents(
                bucket_name, secret_doc_payload)

            self.assertEqual(1, len(created_documents))
            self.assertIn('Certificate', created_documents[0]['schema'])
            self.assertEqual(storage_policy, created_documents[0][
                'metadata']['storagePolicy'])
            self.assertTrue(created_documents[0]['is_secret'])
            self.assertEqual(rand_secret, created_documents[0]['data'])

    def test_create_certificate_key(self):
        rand_secret = {'secret': test_utils.rand_password()}
        bucket_name = test_utils.rand_name('bucket')

        for storage_policy in ('encrypted', 'cleartext'):
            secret_doc_payload = self.secrets_factory.gen_test(
                'CertificateKey', storage_policy, rand_secret)
            created_documents = self.create_documents(
                bucket_name, secret_doc_payload)

            self.assertEqual(1, len(created_documents))
            self.assertIn('CertificateKey', created_documents[0]['schema'])
            self.assertEqual(storage_policy, created_documents[0][
                'metadata']['storagePolicy'])
            self.assertTrue(created_documents[0]['is_secret'])
            self.assertEqual(rand_secret, created_documents[0]['data'])

    def test_create_passphrase(self):
        rand_secret = {'secret': test_utils.rand_password()}
        bucket_name = test_utils.rand_name('bucket')

        for storage_policy in ('encrypted', 'cleartext'):
            secret_doc_payload = self.secrets_factory.gen_test(
                'Passphrase', storage_policy, rand_secret)
            created_documents = self.create_documents(
                bucket_name, secret_doc_payload)

            self.assertEqual(1, len(created_documents))
            self.assertIn('Passphrase', created_documents[0]['schema'])
            self.assertEqual(storage_policy, created_documents[0][
                'metadata']['storagePolicy'])
            self.assertTrue(created_documents[0]['is_secret'])
            self.assertEqual(rand_secret, created_documents[0]['data'])

    def test_delete_document(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, payload)

        documents = self.create_documents(bucket_name, [])
        self.assertEqual(1, len(documents))
        self.assertTrue(documents[0]['deleted'])
        self.assertTrue(documents[0]['deleted_at'])
        self.assertEqual(documents[0]['schema'], payload['schema'])
        self.assertEqual(documents[0]['name'], payload['metadata']['name'])
        self.assertEmpty(documents[0]['metadata'])
        self.assertEmpty(documents[0]['data'])

    def test_delete_all_documents(self):
        payload = self.documents_factory.gen_test(self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        self.assertIsInstance(documents, list)
        self.assertEqual(3, len(documents))

        documents = self.create_documents(bucket_name, [])

        for idx in range(3):
            self.assertTrue(documents[idx]['deleted'])
            self.assertTrue(documents[idx]['deleted_at'])
            self.assertEqual(documents[idx]['schema'], payload[idx]['schema'])
            self.assertEqual(documents[idx]['name'],
                             payload[idx]['metadata']['name'])
            self.assertEmpty(documents[idx]['metadata'])
            self.assertEmpty(documents[idx]['data'])

    def test_delete_and_create_document_in_same_payload(self):
        payload = self.documents_factory.gen_test(self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        # Create just 1 document.
        documents = self.create_documents(bucket_name, payload[0])

        # Create the document in payload[0] but create a new document for
        # payload[1].
        documents = self.create_documents(bucket_name, payload[1])
        # Information about the deleted and created document should've been
        # returned. The 1st document is the deleted one and the 2nd document
        # is the created one.
        self.assertEqual(2, len(documents))
        # Check that deleted doc is formatted correctly.
        self.assertTrue(documents[0]['deleted'])
        self.assertTrue(documents[0]['deleted_at'])
        self.assertEmpty(documents[0]['metadata'])
        self.assertEmpty(documents[0]['data'])
        # Check that created doc isn't deleted.
        self.assertFalse(documents[1]['deleted'])

        for idx in range(2):
            self.assertEqual(documents[idx]['schema'], payload[idx]['schema'])
            self.assertEqual(documents[idx]['name'],
                             payload[idx]['metadata']['name'])

    def test_delete_and_create_many_documents_in_same_payload(self):
        payload = self.documents_factory.gen_test(self.document_mapping)
        bucket_name = test_utils.rand_name('bucket')
        # Create just 1 document.
        documents = self.create_documents(bucket_name, payload[1:])

        # Create the document in payload[0] but create a new document for
        # payload[1].
        documents = self.create_documents(bucket_name, payload[0])
        # The first document will be first, followed by the two deleted docs.
        documents = sorted(documents, key=lambda d: d['deleted'])
        # Information about the deleted and created document should've been
        # returned. The 1st document is the deleted one and the 2nd document
        # is the created one.
        self.assertEqual(3, len(documents))
        self.assertFalse(documents[0]['deleted'])
        self.assertFalse(documents[0]['deleted_at'])
        self.assertTrue(documents[1]['deleted'])
        self.assertTrue(documents[2]['deleted'])
        self.assertTrue(documents[1]['deleted_at'])
        self.assertTrue(documents[2]['deleted_at'])

        for idx in range(1, 3):
            self.assertEqual(documents[idx]['schema'], payload[idx]['schema'])
            self.assertEqual(documents[idx]['name'],
                             payload[idx]['metadata']['name'])
            self.assertEmpty(documents[idx]['metadata'])
            self.assertEmpty(documents[idx]['data'])
