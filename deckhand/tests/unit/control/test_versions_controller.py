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

from deckhand.tests.unit.control import base as test_base


class TestVersionsController(test_base.BaseControllerTest):

    def test_list_versions(self):
        resp = self.app.simulate_get(
            '/versions', headers={'Content-Type': 'application/x-yaml'})
        expected = {
            'v1.0': {
                'path': '/api/v1.0',
                'status': 'stable'
            }
        }
        self.assertEqual(200, resp.status_code)
        self.assertEqual(expected, yaml.safe_load(resp.text))
