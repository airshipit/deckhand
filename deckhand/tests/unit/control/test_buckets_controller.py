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
from oslo_config import cfg

from deckhand.control import buckets
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.control import base as test_base

CONF = cfg.CONF


class TestBucketsController(test_base.BaseControllerTest):
    """Test suite for validating positive scenarios for buckets controller."""

    def test_put_empty_bucket(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all([]))
        self.assertEqual(200, resp.status_code)
        created_documents = list(yaml.safe_load_all(resp.text))
        self.assertEmpty(created_documents)

    def test_put_bucket(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(2, [1, 1])
        document_mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]}
        }
        payload = documents_factory.gen_test(document_mapping)

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        created_documents = list(yaml.safe_load_all(resp.text))
        self.assertEqual(3, len(created_documents))
        expected = sorted([(d['schema'], d['metadata']['name'])
                           for d in payload])
        actual = sorted([(d['schema'], d['metadata']['name'])
                         for d in created_documents])
        self.assertEqual(expected, actual)

    def test_put_bucket_with_secret(self):
        def _do_test(payload):
            bucket_name = test_utils.rand_name('bucket')
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/%s/documents' % bucket_name,
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
            self.assertEqual(200, resp.status_code)
            created_documents = list(yaml.safe_load_all(resp.text))

            self.assertEqual(len(payload), len(created_documents))
            expected = sorted([(d['schema'], d['metadata']['name'])
                               for d in payload])
            actual = sorted([(d['schema'], d['metadata']['name'])
                             for d in created_documents])
            self.assertEqual(expected, actual)
            self.assertEqual(payload[0]['data'], created_documents[0]['data'])

        # Verify whether creating a cleartext secret works.
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'cleartext')]
        _do_test(payload)

        # Verify whether creating an encrypted secret works.
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'encrypted')]

        with mock.patch.object(buckets.BucketsResource, 'secrets_mgr',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = payload[0]['data']
            _do_test(payload)

        # Verify whether any document can be encrypted if its
        # `metadata.storagePolicy`='encrypted'. In the case below,
        # a generic document is tested.
        documents_factory = factories.DocumentFactory(1, [1])
        document = documents_factory.gen_test({}, global_abstract=False)[-1]
        document['metadata']['storagePolicy'] = 'encrypted'

        data_schema_factory = factories.DataSchemaFactory()
        data_schema = data_schema_factory.gen_test(document['schema'], {})

        with mock.patch.object(buckets.BucketsResource, 'secrets_mgr',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = document['data']
            _do_test([document, data_schema])

    def test_create_delete_then_recreate_document_in_different_bucket(self):
        """Ordiniarly creating a document with the same metadata.name/schema
        in a separate bucket raises an exception, but if we delete the document
        and re-create it in a different bucket this should be a success
        scenario.
        """
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        payload = factories.DocumentFactory(2, [1, 1]).gen_test({})
        bucket_name = test_utils.rand_name('bucket')
        alt_bucket_name = test_utils.rand_name('bucket')

        # Create the documents in the first bucket.
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/%s/documents' % bucket_name,
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        documents = list(yaml.safe_load_all(resp.text))
        self.assertEqual(3, len(documents))
        self.assertEqual([bucket_name] * 3,
                         [d['status']['bucket'] for d in documents])

        # Delete the documents from the first bucket.
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/%s/documents' % bucket_name,
            headers={'Content-Type': 'application/x-yaml'}, body=None)
        self.assertEqual(200, resp.status_code)

        # Re-create the documents in the second bucket.
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/%s/documents' % alt_bucket_name,
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        documents = list(yaml.safe_load_all(resp.text))
        self.assertEqual(3, len(documents))
        self.assertEqual([alt_bucket_name] * 3,
                         [d['status']['bucket'] for d in documents])


class TestBucketsControllerNegative(test_base.BaseControllerTest):
    """Test suite for validating negative scenarios for bucket controller."""

    def test_put_conflicting_layering_policy(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        payload = factories.DocumentFactory(1, [1]).gen_test({})[0]

        # Create the first layering policy.
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all([payload]))
        self.assertEqual(200, resp.status_code)

        # Validate that a layering policy with a different, conflicting name
        # raises the expected exception.
        error_re = ('.*A singleton document by the name %s already exists in '
                    'the system.' % payload['metadata']['name'])
        payload['metadata']['name'] = test_utils.rand_name('layering-policy')
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all([payload]))
        self.assertEqual(409, resp.status_code)
        resp_error = ' '.join(resp.text.split())
        self.assertRegexpMatches(resp_error, error_re)

    def test_put_conflicting_document(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        payload = factories.DocumentFactory(1, [1]).gen_test({})[0]
        bucket_name = test_utils.rand_name('bucket')
        alt_bucket_name = test_utils.rand_name('bucket')
        # Create document in `bucket_name`.
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/%s/documents' % bucket_name,
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all([payload]))
        # Create same document in `alt_bucket_name` and validate conflict.
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/%s/documents' % alt_bucket_name,
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all([payload]))
        self.assertEqual(409, resp.status_code)


class TestBucketsControllerNegativeRBAC(test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for bucket
    controller.
    """

    def test_put_bucket_cleartext_documents_except_forbidden(self):
        rules = {'deckhand:create_cleartext_documents': 'rule:admin_api'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(2, [1, 1])
        payload = documents_factory.gen_test({})

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(403, resp.status_code)

    def test_put_bucket_encrypted_document_except_forbidden(self):
        rules = {'deckhand:create_encrypted_documents': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'encrypted')]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(403, resp.status_code)
