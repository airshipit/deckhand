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

from deckhand import factories
from deckhand.tests.unit.control import base as test_base


class TestRevisionTagsControllerNegativeRBAC(test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for revision tags
    controller.
    """

    def setUp(self):
        super(TestRevisionTagsControllerNegativeRBAC, self).setUp()
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a revision to tag.
        secrets_factory = factories.DocumentSecretFactory()
        payload = [secrets_factory.gen_test('Certificate', 'cleartext')]
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        self.revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

    def test_revision_list_tags_except_forbidden(self):
        rules = {'deckhand:list_tags': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/tags' % self.revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_revision_show_tag_except_forbidden(self):
        rules = {'deckhand:create_tag': '@',
                 'deckhand:show_tag': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_post(
            '/api/v1.0/revisions/%s/tags/%s' % (self.revision_id, 'test'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(201, resp.status_code)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/tags/test' % self.revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_revision_create_tag_except_forbidden(self):
        rules = {'deckhand:create_tag': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_post(
            '/api/v1.0/revisions/%s/tags/%s' % (self.revision_id, 'test'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_revision_delete_tag_except_forbidden(self):
        rules = {'deckhand:create_tag': '@',
                 'deckhand:delete_tag': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_post(
            '/api/v1.0/revisions/%s/tags/%s' % (self.revision_id, 'test'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(201, resp.status_code)

        resp = self.app.simulate_delete(
            '/api/v1.0/revisions/%s/tags/%s' % (self.revision_id, 'test'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_revision_delete_all_tags_except_forbidden(self):
        rules = {'deckhand:delete_tags': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_delete(
            '/api/v1.0/revisions/%s/tags' % self.revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)
