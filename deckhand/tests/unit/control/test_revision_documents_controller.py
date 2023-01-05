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

from unittest import mock

from deckhand.common.document import DocumentDict as document_dict
from deckhand.engine import secrets_manager
from deckhand import factories
from deckhand.tests.unit.control import base as test_base


class TestRevisionDocumentsController(test_base.BaseControllerTest):

    def test_list_revision_documents_with_yaml_anchors_and_pointers(self):
        """Test that Deckhand accepts and parses documents that use YAML
        anchors and pointers.
        """
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents = """
---
schema: aic/Versions/v1
metadata:
  name: with-anchor
  schema: metadata/Document/v1
  storagePolicy: cleartext
  labels:
    selector: foo1
  layeringDefinition:
    abstract: True
    layer: global
data:
  conf: &anchor
    path:
      to:
        something:
          important:
            value
  copy: *anchor
---
schema: deckhand/LayeringPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: layering-policy
data:
  layerOrder:
    - global
...
"""

        expected_data_section = {
            'conf': {
                'path': {
                    'to': {
                        'something': {
                            'important': 'value'
                        }
                    }
                }
            },
            'copy': {
                'path': {
                    'to': {
                        'something': {
                            'important': 'value'
                        }
                    }
                }
            }
        }

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=documents)
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            params={'sort': 'schema'}, params_csv=False,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        retrieved_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(2, len(retrieved_documents))
        self.assertEqual(expected_data_section, retrieved_documents[0]['data'])

    def _setup_payload(self):
        data = '12345'
        sub_src = '.source1'
        sub_dest = '.destination2'
        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'encrypted')]
        payload[0]['data'] = data
        sub1 = {'src': {'schema': 'pegleg/SoftwareVersions/v1', 'name': 'sub1',
                'path': sub_src}, 'dest': {'path': '.destination1'}}
        sub2 = {'src': {'schema': 'pegleg/SoftwareVersions/v1', 'name': 'sub2',
                'path': '.source2'}, 'dest': {'path': sub_dest}}
        payload[0]['metadata']['substitutions'] = [sub1, sub2]
        return payload, data, sub_src, sub_dest

    def test_list_encrypted_revision_documents_redacted(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        payload, data, sub_src, sub_dest = self._setup_payload()

        with mock.patch.object(secrets_manager, 'SecretsManager',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = payload[0]['data']
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was redacted.
        redacted_data = document_dict.redact(data)
        redacted_sub_src = document_dict.redact(sub_src)
        redacted_sub_dest = document_dict.redact(sub_dest)
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'},
            query_string='cleartext-secrets=false')

        self.assertEqual(200, resp.status_code)
        self.assertNotEqual(list(yaml.safe_load_all(resp.text)), [])
        response_yaml = list(yaml.safe_load_all(resp.text))
        self.assertEqual(redacted_data, response_yaml[0]['data'])
        subs = response_yaml[0]['metadata']['substitutions']
        self.assertEqual(redacted_sub_src, subs[0]['src']['path'])
        self.assertEqual(redacted_sub_dest, subs[1]['dest']['path'])

    def test_list_encrypted_revision_documents_cleartext_secrets(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        payload, data, sub_src, sub_dest = self._setup_payload()

        with mock.patch.object(secrets_manager, 'SecretsManager',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = payload[0]['data']
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was not redacted.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'},
            query_string='cleartext-secrets=true')

        self.assertEqual(200, resp.status_code)
        self.assertNotEqual(list(yaml.safe_load_all(resp.text)), [])
        response_yaml = list(yaml.safe_load_all(resp.text))
        self.assertEqual(data, response_yaml[0]['data'])
        subs = response_yaml[0]['metadata']['substitutions']
        self.assertEqual(sub_src, subs[0]['src']['path'])
        self.assertEqual(sub_dest, subs[1]['dest']['path'])


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
        with mock.patch.object(secrets_manager, 'SecretsManager',
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

    def test_list_revision_documents_sorting_by_schema_then_limit(self):
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
        schemas = ['deckhand/Certificate/v1',
                   'deckhand/CertificateKey/v1',
                   'deckhand/LayeringPolicy/v1']
        for idx in range(len(documents)):
            documents[idx]['schema'] = schemas[idx]

        for limit in (0, 1, 2, 3):
            expected_schemas = schemas[:limit]

            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(documents))
            self.assertEqual(200, resp.status_code)
            revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
                'revision']

            resp = self.app.simulate_get(
                '/api/v1.0/revisions/%s/documents' % revision_id,
                params={'sort': 'schema', 'limit': limit}, params_csv=False,
                headers={'Content-Type': 'application/x-yaml'})
            self.assertEqual(200, resp.status_code)
            retrieved_documents = list(yaml.safe_load_all(resp.text))

            self.assertEqual(limit, len(retrieved_documents))
            self.assertEqual(expected_schemas,
                             [d['schema'] for d in retrieved_documents])
