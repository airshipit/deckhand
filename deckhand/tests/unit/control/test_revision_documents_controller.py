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

import yaml

import mock

from deckhand.control import buckets
from deckhand import factories
from deckhand.tests.unit.control import base as test_base


class TestRevisionDocumentsControllerNegativeRBAC(
        test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for revision documents
    controller.

    For these tests, if policy enforcement fails, the response body should be
    empty.
    """

    def test_list_cleartext_revision_documents_insufficient_permissions(self):
        rules = {'deckhand:list_cleartext_documents': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'cleartext')]
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was not returned.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_list_encrypted_revision_documents_insufficient_permissions(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'encrypted')]
        with mock.patch.object(buckets.BucketsResource, 'secrets_mgr',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = payload[0]['data']
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was not returned.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        self.assertEmpty(list(yaml.safe_load_all(resp.text)))


class TestRevisionDocumentsControllerSorting(test_base.BaseControllerTest):

    def test_list_revision_documents_sorting_metadata_name(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(2, [1, 1])
        documents = documents_factory.gen_test({
            '_SITE_ACTIONS_1_': {
                'actions': [{'method': 'merge', 'path': '.'}]
            }
        })
        expected_names = ['bar', 'baz', 'foo']
        for idx in range(len(documents)):
            documents[idx]['metadata']['name'] = expected_names[idx]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(documents))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            params={'sort': 'metadata.name'}, params_csv=False,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        retrieved_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(3, len(retrieved_documents))
        self.assertEqual(expected_names,
                         [d['metadata']['name'] for d in retrieved_documents])

    def test_list_revision_documents_sorting_by_metadata_name_and_schema(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(2, [1, 1])
        documents = documents_factory.gen_test({
            '_SITE_ACTIONS_1_': {
                'actions': [{'method': 'merge', 'path': '.'}]
            }
        })
        expected_names = ['foo', 'baz', 'bar']
        expected_schemas = ['deckhand/Certificate/v1',
                            'deckhand/Certificate/v1',
                            'deckhand/LayeringPolicy/v1']
        for idx in range(len(documents)):
            documents[idx]['metadata']['name'] = expected_names[idx]
            documents[idx]['schema'] = expected_schemas[idx]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(documents))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            params={'sort': ['schema', 'metadata.name']}, params_csv=False,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        retrieved_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(3, len(retrieved_documents))
        self.assertEqual(['baz', 'foo', 'bar'],
                         [d['metadata']['name'] for d in retrieved_documents])
        self.assertEqual(expected_schemas,
                         [d['schema'] for d in retrieved_documents])

    def test_list_revision_documents_sorting_by_schema(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(2, [1, 1])
        documents = documents_factory.gen_test({
            '_SITE_ACTIONS_1_': {
                'actions': [{'method': 'merge', 'path': '.'}]
            }
        })
        expected_schemas = ['deckhand/Certificate/v1',
                            'deckhand/CertificateKey/v1',
                            'deckhand/LayeringPolicy/v1']
        for idx in range(len(documents)):
            documents[idx]['schema'] = expected_schemas[idx]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(documents))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            params={'sort': 'schema'}, params_csv=False,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        retrieved_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(3, len(retrieved_documents))
        self.assertEqual(expected_schemas,
                         [d['schema'] for d in retrieved_documents])
