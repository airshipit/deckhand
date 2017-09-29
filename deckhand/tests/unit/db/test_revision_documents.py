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

from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestRevisionDocumentsFiltering(base.TestDbBase):

    def test_document_filtering_by_bucket_name(self):
        document = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, document)

        revision_id = self.create_documents(bucket_name, [])[0]['revision_id']

        filters = {'bucket_name': bucket_name}
        retrieved_documents = self.list_revision_documents(
            revision_id, **filters)

        self.assertEqual(1, len(retrieved_documents))
        self.assertEqual(bucket_name, retrieved_documents[0]['bucket_name'])
