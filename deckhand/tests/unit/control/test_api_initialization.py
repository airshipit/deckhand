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

import inspect
import os

import mock

from deckhand.common import utils
from deckhand.control import api
from deckhand.control import buckets
from deckhand.control import health
from deckhand.control import revision_deepdiffing
from deckhand.control import revision_diffing
from deckhand.control import revision_documents
from deckhand.control import revision_tags
from deckhand.control import revisions
from deckhand.control import rollback
from deckhand.control import validations
from deckhand.control import versions
from deckhand.tests.unit import base as test_base


class TestApi(test_base.DeckhandTestCase):

    def setUp(self):
        super(TestApi, self).setUp()
        # Mock the API resources.
        for resource in (
            buckets, health, revision_deepdiffing, revision_diffing,
                revision_documents, revision_tags, revisions, rollback,
                validations, versions):
            class_names = self._get_module_class_names(resource)
            for class_name in class_names:
                resource_obj = self.patchobject(
                    resource, class_name, autospec=True)
                setattr(self, utils.to_snake_case(class_name), resource_obj)

        # Mock the location of the configuration files for API initialization.
        curr_path = os.path.dirname(os.path.realpath(__file__))
        repo_path = os.path.join(
            curr_path, os.pardir, os.pardir, os.pardir, os.pardir)
        temp_config_files = {
            'conf': os.path.join(
                repo_path, 'etc', 'deckhand', 'deckhand.conf.sample'),
            'paste': os.path.join(
                repo_path, 'etc', 'deckhand', 'deckhand-paste.ini')
        }
        mock_get_config_files = self.patchobject(
            api, '_get_config_files', autospec=True)
        mock_get_config_files.return_value = temp_config_files

    def _get_module_class_names(self, module):
        class_names = [obj.__name__ for name, obj in inspect.getmembers(module)
                       if inspect.isclass(obj)]
        return class_names

    @mock.patch.object(api, 'policy', autospec=True)
    @mock.patch.object(api, 'db_api', autospec=True)
    @mock.patch.object(api, 'logging', autospec=True)
    @mock.patch('deckhand.service.falcon', autospec=True)
    def test_init_application(self, mock_falcon, mock_logging,
                              mock_db_api, _):
        mock_falcon_api = mock_falcon.API.return_value
        self.override_config(
            'connection', mock.sentinel.db_connection, group='database')

        api.init_application()

        mock_falcon_api.add_route.assert_has_calls([
            mock.call('/api/v1.0/buckets/{bucket_name}/documents',
                      self.buckets_resource()),
            mock.call('/api/v1.0/health', self.health_resource()),
            mock.call('/api/v1.0/revisions', self.revisions_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}',
                      self.revisions_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/deepdiff/'
                      '{comparison_revision_id}',
                      self.revision_deep_diffing_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/diff/'
                      '{comparison_revision_id}',
                      self.revision_diffing_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/documents',
                      self.revision_documents_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/rendered-documents',
                      self.rendered_documents_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/tags',
                      self.revision_tags_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/tags/{tag}',
                      self.revision_tags_resource()),
            mock.call('/api/v1.0/rollback/{revision_id}',
                      self.rollback_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/validations',
                      self.validations_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/validations/'
                      '{validation_name}',
                      self.validations_resource()),
            mock.call('/api/v1.0/revisions/{revision_id}/validations/'
                      '{validation_name}/entries/{entry_id}',
                      self.validations_resource()),
            mock.call('/versions', self.versions_resource())
        ], any_order=True)

        mock_db_api.setup_db.assert_called_once_with(
            str(mock.sentinel.db_connection))
