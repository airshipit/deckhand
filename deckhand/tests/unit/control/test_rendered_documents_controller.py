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


class TestRenderedDocumentsControllerNegativeRBAC(
        test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for rendered documents
    controller.
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
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
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
            mock_secrets_mgr.create.return_value = {
                'secret': payload[0]['data']}
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was not returned.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        self.assertEmpty(list(yaml.safe_load_all(resp.text)))
