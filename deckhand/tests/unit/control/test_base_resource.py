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

import mock

from deckhand.control import base as api_base
from deckhand.tests.unit.control import base as test_base


class TestBaseResource(test_base.BaseControllerTest):

    def setUp(self):
        super(TestBaseResource, self).setUp()
        self.base_resource = api_base.BaseResource()

    @mock.patch.object(api_base, 'dir')  # noqa
    def test_on_options(self, mock_dir):
        expected_methods = ['on_get', 'on_post', 'on_put', 'on_delete',
                            'on_patch']
        mock_dir.return_value = expected_methods
        mock_resp = mock.Mock(headers={})
        self.base_resource.on_options(None, mock_resp)

        self.assertIn('Allow', mock_resp.headers)
        self.assertEqual('GET,POST,PUT,DELETE,PATCH',
                         mock_resp.headers['Allow'])
        self.assertEqual('200 OK', mock_resp.status)
