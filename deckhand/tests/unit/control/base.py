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

from falcon import testing as falcon_testing

from deckhand import service
from deckhand.tests.unit import base as test_base
from deckhand.tests.unit import fixtures


class BaseControllerTest(test_base.DeckhandWithDBTestCase,
                         falcon_testing.TestCase):
    """Base class for unit testing falcon controllers."""

    def setUp(self):
        super(BaseControllerTest, self).setUp()
        self.app = falcon_testing.TestClient(
            service.deckhand_app_factory(None))
        self.policy = self.useFixture(fixtures.RealPolicyFixture())
        # NOTE: allow_anonymous_access allows these unit tests to get around
        # Keystone authentication.
        self.useFixture(fixtures.ConfPatcher(allow_anonymous_access=True))

    def tearDown(self):
        super(BaseControllerTest, self).tearDown()
        # Validate whether policy enforcement happened the way we expected it
        # to. This check is really only meaningful if ``self.policy.set_rules``
        # is used within the context of a test that inherits from this class.
        self.assertTrue(
            set(self.policy.expected_policy_actions) ==
            set(self.policy.actual_policy_actions),
            'The expected policy actions passed to ``self.policy.set_rules`` '
            'do not match the policy actions that were actually enforced by '
            'Deckhand. Set of expected policies %s should be equal to set of '
            'actual policies: %s. There is either a bug with the test or with '
            'policy enforcement in the controller.' % (
                self.policy.expected_policy_actions,
                self.policy.actual_policy_actions))
