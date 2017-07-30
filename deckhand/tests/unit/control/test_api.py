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

import testtools

from deckhand.control import api
from deckhand.control import base as api_base
from deckhand.control import documents
from deckhand.control import revision_documents
from deckhand.control import revisions
from deckhand.control import secrets


class TestApi(testtools.TestCase):

    def setUp(self):
        super(TestApi, self).setUp()
        for resource in (documents, revisions, revision_documents, secrets):
            resource_name = resource.__name__.split('.')[-1]
            resource_obj = mock.patch.object(
                resource, '%sResource' % resource_name.title().replace('_', '')
            ).start()
            setattr(self, '%s_resource' % resource_name, resource_obj)

    @mock.patch.object(api, 'db_api', autospec=True)
    @mock.patch.object(api, 'config', autospec=True)
    @mock.patch.object(api, 'falcon', autospec=True)
    def test_start_api(self, mock_falcon,
                       mock_config, mock_db_api):
        mock_falcon_api = mock_falcon.API.return_value

        result = api.start_api()
        self.assertEqual(mock_falcon_api, result)

        mock_falcon.API.assert_called_once_with(
            request_type=api_base.DeckhandRequest)
        mock_falcon_api.add_route.assert_has_calls([
            mock.call('/api/v1.0/documents', self.documents_resource()),
            mock.call('/api/v1.0/revisions', self.revisions_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/documents',
                      self.revision_documents_resource()),
            mock.call('/api/v1.0/secrets', self.secrets_resource())
        ])
        mock_config.parse_args.assert_called_once_with()
        mock_db_api.setup_db.assert_called_once_with()
