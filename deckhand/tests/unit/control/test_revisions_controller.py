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

import os

import mock
import yaml

from deckhand.engine import secrets_manager
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.control import base as test_base


class TestRevisionsController(test_base.BaseControllerTest):

    def test_delete_revisions_also_deletes_barbican_secrets(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_encrypted_documents': '@',
                 'deckhand:delete_revisions': '@'}
        self.policy.set_rules(rules)

        resource_path = os.path.join(os.getcwd(), 'deckhand', 'tests', 'unit',
                                     'resources', 'sample_passphrase.yaml')
        with open(resource_path) as f:
            encrypted_document = f.read()

        fake_secret_ref = test_utils.rand_barbican_ref()
        with mock.patch.object(secrets_manager, 'SecretsManager',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = fake_secret_ref

            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=encrypted_document)
            self.assertEqual(200, resp.status_code)

        with mock.patch.object(secrets_manager.SecretsManager,
                               'barbican_driver', autospec=True) \
                as m_barbican_driver:
            resp = self.app.simulate_delete(
                '/api/v1.0/revisions',
                headers={'Content-Type': 'application/x-yaml'})

            self.assertEqual(204, resp.status_code)
            m_barbican_driver.delete_secret.assert_called_once_with(
                fake_secret_ref)


class TestRevisionsControllerNegativeRBAC(test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for revisions
    controller.
    """

    def test_list_revisions_except_forbidden(self):
        rules = {'deckhand:list_revisions': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions',
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_show_revision_except_forbidden(self):
        rules = {'deckhand:show_revision': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a bucket with a document to generate a revision_id.
        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'cleartext')]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Then try to query the revision "show" endpoint with insufficient
        # permissions.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_delete_revisions_except_forbidden(self):
        rules = {'deckhand:delete_revisions': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_delete(
            '/api/v1.0/revisions',
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)
