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

from deckhand.control.views import document
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestRevisionViews(base.TestDbBase):

    def setUp(self):
        super(TestRevisionViews, self).setUp()
        self.view_builder = document.ViewBuilder()
        self.factory = factories.ValidationPolicyFactory()

    def _test_document_creation_view(self, count):
        # Test document creation view with the number of documents being
        # created specified by `count`.
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(count)]
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        document_view = self.view_builder.list(created_documents)

        self.assertIsInstance(document_view, list)
        self.assertEqual(count, len(document_view))

        expected_attrs = ('id', 'status', 'metadata', 'data', 'schema')
        for idx in range(count):
            for attr in expected_attrs:
                self.assertIn(attr, document_view[idx])
            for attr in ('bucket', 'revision'):
                self.assertIn(attr, document_view[idx]['status'])

    def test_create_single_document(self):
        self._test_document_creation_view(1)

    def test_create_many_documents(self):
        self._test_document_creation_view(4)
