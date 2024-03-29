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

from deckhand.engine import secrets_manager
from deckhand import factories
from deckhand.tests.unit.control import base as test_base


class TestRevisionsRollbackController(test_base.BaseControllerTest):
    """Test basic scenarios for the ``RollbackResource`` controller."""

    def test_rollback_to_revision_0(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_revisions': '@'}
        self.policy.set_rules(rules)

        # Create revision 1.
        documents_factory = factories.DocumentFactory(1, [1])
        payload = documents_factory.gen_test({})
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)

        # Rollback to revision 0 (thereby creating revision 1 in effect).
        resp = self.app.simulate_post(
            '/api/v1.0/rollback/%s' % 0,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(201, resp.status_code)

        # Validate that 2 revisions now exist.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions',
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        self.assertEqual(2, yaml.safe_load(resp.text)['count'])


class TestRevisionsRollbackControllerNegativeRBAC(
        test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for revisions rollback
    controller.
    """

    def test_revision_rollback_cleartext_except_forbidden(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a revision so we have something to roll back to.
        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'cleartext')]
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        rules = {'deckhand:create_cleartext_documents': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_post(
            '/api/v1.0/rollback/%s' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_revision_rollback_encrypted_except_forbidden(self):
        rules = {'deckhand:create_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a revision so we have something to roll back to.
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

        rules = {'deckhand:create_encrypted_documents': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_post(
            '/api/v1.0/rollback/%s' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)
