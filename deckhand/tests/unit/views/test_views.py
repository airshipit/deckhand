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

from deckhand.control.views import revision
from deckhand.tests.unit.db import base
from deckhand.tests import test_utils


class TestRevisionViews(base.TestDbBase):

    def setUp(self):
        super(TestRevisionViews, self).setUp()
        self.view_builder = revision.ViewBuilder()

    def test_list_revisions(self):
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        self._create_documents(payload)
        revisions = self._list_revisions()
        revisions_view = self.view_builder.list(revisions)

        expected_attrs = ('next', 'prev', 'results', 'count')
        for attr in expected_attrs:
            self.assertIn(attr, revisions_view)
        # Validate that only 1 revision was returned.
        self.assertEqual(1, revisions_view['count'])
        # Validate that the first revision has 4 documents.
        self.assertIn('id', revisions_view['results'][0])
        self.assertIn('count', revisions_view['results'][0])
        self.assertEqual(4, revisions_view['results'][0]['count'])

    def test_list_many_revisions(self):
        docs_count = []
        for _ in range(3):
            doc_count = test_utils.rand_int(3, 9)
            docs_count.append(doc_count)

            payload = [base.DocumentFixture.get_minimal_fixture()
                       for _ in range(doc_count)]
            self._create_documents(payload)
            revisions = self._list_revisions()
        revisions_view = self.view_builder.list(revisions)

        expected_attrs = ('next', 'prev', 'results', 'count')
        for attr in expected_attrs:
            self.assertIn(attr, revisions_view)
        # Validate that only 1 revision was returned.
        self.assertEqual(3, revisions_view['count'])

        # Validate that each revision has correct number of documents.
        for idx, doc_count in enumerate(docs_count):
            self.assertIn('count', revisions_view['results'][idx])
            self.assertIn('id', revisions_view['results'][idx])
            self.assertEqual(doc_count, revisions_view['results'][idx][
                'count'])

    def test_show_revision(self):
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        documents = self._create_documents(payload)
        revision = self._get_revision(documents[0]['revision_id'])
        revision_view = self.view_builder.show(revision)

        expected_attrs = ('id', 'url', 'createdAt', 'validationPolicies')
        for attr in expected_attrs:
            self.assertIn(attr, revision_view)
        self.assertIsInstance(revision_view['validationPolicies'], list)
