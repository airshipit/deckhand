#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import falcon
import mock
from oslo_policy import policy as common_policy

from deckhand.control import base as api_base
import deckhand.policy
from deckhand.tests.unit import base as test_base
from deckhand.tests.unit import policy_fixture


class PolicyBaseTestCase(test_base.DeckhandTestCase):

    def setUp(self):
        super(PolicyBaseTestCase, self).setUp()
        # The default policies in deckhand.policies are automatically
        # registered. Override them with custom rules. '@' allows anyone to
        # perform a policy action.
        self.rules = {
            "deckhand:create_cleartext_documents": [['@']],
            "deckhand:list_cleartext_documents": [['rule:admin_api']]
        }

        self.policy = self.useFixture(policy_fixture.RealPolicyFixture())
        self._set_rules()

    def _set_rules(self):
        these_rules = common_policy.Rules.from_dict(self.rules)
        deckhand.policy._ENFORCER.set_rules(these_rules)

    def _enforce_policy(self, action):
        api_args = self._get_args()

        @deckhand.policy.authorize(action)
        def noop(*args, **kwargs):
            pass

        noop(*api_args)

    def _get_args(self):
        # Returns the first two arguments that would be passed to any falcon
        # on_{HTTP_VERB} method: (self (which is mocked), falcon Request obj).
        falcon_req = api_base.DeckhandRequest(mock.MagicMock())
        return (mock.Mock(), falcon_req)


class PolicyPositiveTestCase(PolicyBaseTestCase):

    def test_enforce_allowed_action(self):
        action = "deckhand:create_cleartext_documents"
        self._enforce_policy(action)


class PolicyNegativeTestCase(PolicyBaseTestCase):

    def test_enforce_disallowed_action(self):
        action = "deckhand:list_cleartext_documents"
        error_re = "Policy doesn't allow %s to be performed." % action
        e = self.assertRaises(
            falcon.HTTPForbidden, self._enforce_policy, action)
        self.assertRegexpMatches(error_re, e.description)

    def test_enforce_nonexistent_action(self):
        action = "example:undefined"
        error_re = "Policy %s has not been registered" % action
        e = self.assertRaises(
            falcon.HTTPForbidden, self._enforce_policy, action)
        self.assertRegexpMatches(error_re, e.description)
