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

from deckhand.control import api
from deckhand.control import base
from deckhand.control import buckets
from deckhand.control import revision_diffing
from deckhand.control import revision_documents
from deckhand.control import revision_tags
from deckhand.control import revisions
from deckhand.control import rollback
from deckhand.control import versions
from deckhand.tests.unit import base as test_base


class TestApi(test_base.DeckhandTestCase):

    def setUp(self):
        super(TestApi, self).setUp()
        for resource in (buckets, revision_diffing, revision_documents,
                         revision_tags, revisions, rollback, versions):
            resource_name = resource.__name__.split('.')[-1]
            resource_obj = self.patchobject(
                resource, '%sResource' % resource_name.title().replace(
                    '_', ''), autospec=True)
            setattr(self, '%s_resource' % resource_name, resource_obj)

    @mock.patch.object(api, 'db_api', autospec=True)
    @mock.patch.object(api, 'logging', autospec=True)
    @mock.patch.object(api, 'CONF', autospec=True)
    @mock.patch.object(api, 'falcon', autospec=True)
    def test_start_api(self, mock_falcon, mock_config, mock_logging,
                       mock_db_api):
        mock_falcon_api = mock_falcon.API.return_value

        result = api.start_api()
        self.assertEqual(mock_falcon_api, result)

        mock_falcon.API.assert_called_once_with(
            request_type=base.DeckhandRequest)
        mock_falcon_api.add_route.assert_has_calls([
            mock.call('/api/v1.0/bucket/{bucket_name}/documents',
                      self.buckets_resource()),
            mock.call('/api/v1.0/revisions', self.revisions_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}',
                      self.revisions_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/diff/'
                      '{comparison_revision_id}',
                      self.revision_diffing_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/documents',
                      self.revision_documents_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/tags',
                      self.revision_tags_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/tags/{tag}',
                      self.revision_tags_resource()),
            mock.call('/api/v1.0/rollback/{revision_id}',
                      self.rollback_resource()),
            mock.call('/versions', self.versions_resource())
        ])

        mock_db_api.drop_db.assert_called_once_with()
        mock_db_api.setup_db.assert_called_once_with()
