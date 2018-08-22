# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from deckhand.tests.unit.control import base as test_base


class TestRevisionsDeepDiffControllerNegativeRBAC(
        test_base.BaseControllerTest):

    """Test suite for validating negative RBAC scenarios for revisions deepdiff
    controller.
    """

    def test_show_revision_deepdiff_except_forbidden(self):
        rules = {'deckhand:show_revision_deepdiff': 'rule:admin_api'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/0/deepdiff/0',
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)
