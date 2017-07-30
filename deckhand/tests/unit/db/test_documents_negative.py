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

from deckhand.tests.unit.db import base


class TestDocumentsNegative(base.TestDbBase):

    def test_get_documents_by_revision_id_and_wrong_filters(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        document = self._create_documents(payload)[0]
        filters = {
            'schema': 'fake_schema',
            'metadata.name': 'fake_meta_name',
            'metadata.layeringDefinition.abstract':
                not document['metadata']['layeringDefinition']['abstract'],
            'metadata.layeringDefinition.layer': 'fake_layer',
            'metadata.label': 'fake_label'
        }

        documents = self._get_revision_documents(
            document['revision_id'], **filters)
        self.assertEmpty(documents)

        for filter_key, filter_val in filters.items():
            documents = self._get_revision_documents(
                document['revision_id'], filter_key=filter_val)
            self.assertEmpty(documents)
