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

from deckhand import errors
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestDocumentsNegative(base.TestDbBase):

    def test_get_documents_by_revision_id_and_wrong_filters(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        document = self.create_documents(bucket_name, payload)[0]
        filters = {
            'schema': 'fake_schema',
            'metadata.name': 'fake_meta_name',
            'metadata.layeringDefinition.abstract':
                not document['metadata']['layeringDefinition']['abstract'],
            'metadata.layeringDefinition.layer': 'fake_layer',
            'metadata.label': 'fake_label'
        }

        documents = self.list_revision_documents(
            document['revision_id'], **filters)
        self.assertEmpty(documents)

        for filter_key, filter_val in filters.items():
            documents = self.list_revision_documents(
                document['revision_id'], filter_key=filter_val)
            self.assertEmpty(documents)

    def test_delete_document_invalid_id(self):
        self.assertRaises(errors.DocumentNotFound,
                          self.show_document,
                          id=-1)

    def test_create_bucket_conflict(self):
        # Create the document in one bucket.
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, payload)

        # Verify that the document cannot be created in another bucket.
        alt_bucket_name = test_utils.rand_name('bucket')
        error_re = ("Document with schema %s and metadata.name "
                    "%s already exists in bucket %s." % (
                        payload['schema'], payload['metadata']['name'],
                        bucket_name))
        self.assertRaisesRegex(
            errors.DocumentExists, error_re, self.create_documents,
            alt_bucket_name, payload)
