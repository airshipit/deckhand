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
from deckhand.tests import test_utils
from deckhand.tests.unit import base


class TestDocumentViews(base.DeckhandWithDBTestCase):

    def setUp(self):
        super(TestDocumentViews, self).setUp()
        self.view_builder = document.ViewBuilder()

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

        revision_ids = set([v['status']['revision'] for v in document_view])
        self.assertEqual([1], list(revision_ids))

    def test_create_single_document(self):
        self._test_document_creation_view(1)

    def test_create_many_documents(self):
        self._test_document_creation_view(4)

    def test_delete_all_documents(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, payload)
        deleted_documents = self.create_documents(bucket_name, [])

        document_view = self.view_builder.list(deleted_documents)
        self.assertEqual(1, len(document_view))
        self.assertEqual({'status': {'bucket': bucket_name, 'revision': 2}},
                         document_view[0])
