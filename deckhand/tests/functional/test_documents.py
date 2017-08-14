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

import os
import yaml

import falcon

from deckhand.tests.functional import base as test_base


class TestDocumentsApi(test_base.TestFunctionalBase):

    def _read_test_resource(self, file_name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        test_yaml_path = os.path.abspath(os.path.join(
            dir_path, os.pardir, 'unit', 'resources', file_name + '.yaml'))

        with open(test_yaml_path, 'r') as yaml_file:
            yaml_data = yaml_file.read()
        return yaml_data

    def test_create_document(self):
        yaml_data = self._read_test_resource('sample_document')
        result = self.app.simulate_post('/api/v1.0/documents', body=yaml_data)
        self.assertEqual(falcon.HTTP_201, result.status)

        # Validate that the correct number of documents were created: one
        # document corresponding to ``yaml_data``.
        resp_documents = [d for d in yaml.safe_load_all(result.text)]
        self.assertIsInstance(resp_documents, list)
        self.assertEqual(1, len(resp_documents))
        self.assertIn('revision_id', resp_documents[0])
