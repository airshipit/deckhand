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
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base
from deckhand import types


class TestRevisionViews(base.TestDbBase):

    def setUp(self):
        super(TestRevisionViews, self).setUp()
        self.view_builder = revision.ViewBuilder()
        self.factory = factories.ValidationPolicyFactory()

    def test_list_revisions_with_multiple_documents(self):
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, payload)
        revisions = self.list_revisions()
        revisions_view = self.view_builder.list(revisions)

        self.assertIn('results', revisions_view)
        # Validate that only 1 revision was returned.
        self.assertEqual(1, revisions_view['count'])
        # Validate that the first revision has 4 documents.
        self.assertIn('id', revisions_view['results'][0])

    def test_list_multiple_revisions(self):
        docs_count = []
        for _ in range(3):
            doc_count = test_utils.rand_int(3, 9)
            docs_count.append(doc_count)

            payload = [base.DocumentFixture.get_minimal_fixture()
                       for _ in range(doc_count)]
            bucket_name = test_utils.rand_name('bucket')
            self.create_documents(bucket_name, payload)
            revisions = self.list_revisions()
        revisions_view = self.view_builder.list(revisions)

        self.assertIn('results', revisions_view)
        # Validate that only 1 revision was returned.
        self.assertEqual(3, revisions_view['count'])

        # Validate that each revision has correct number of documents.
        for idx, doc_count in enumerate(docs_count):
            self.assertIn('id', revisions_view['results'][idx])

    def test_show_revision(self):
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        # Validate that each document points to the same revision.
        revision_ids = set([d['revision_id'] for d in documents])
        self.assertEqual(1, len(revision_ids))

        revision = self.show_revision(documents[0]['revision_id'])
        revision_view = self.view_builder.show(revision)

        expected_attrs = ('id', 'url', 'createdAt', 'validationPolicies',
                          'status')
        for attr in expected_attrs:
            self.assertIn(attr, revision_view)

        self.assertIsInstance(revision_view['validationPolicies'], list)
        self.assertEqual(revision_view['validationPolicies'], [])

    def test_show_revision_successful_validation_policy(self):
        # Simulate 4 document payload with an internally generated validation
        # policy which executes 'deckhand-schema-validation'.
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        validation_policy = self.factory.gen(types.DECKHAND_SCHEMA_VALIDATION,
                                             status='success')
        payload.append(validation_policy)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        revision = self.show_revision(documents[0]['revision_id'])
        revision_view = self.view_builder.show(revision)

        expected_attrs = ('id', 'url', 'createdAt', 'validationPolicies',
                          'status')

        for attr in expected_attrs:
            self.assertIn(attr, revision_view)

        self.assertEqual('success', revision_view['status'])
        self.assertIsInstance(revision_view['validationPolicies'], list)
        self.assertEqual(1, len(revision_view['validationPolicies']))
        self.assertEqual(revision_view['validationPolicies'][0]['name'],
                         'deckhand-schema-validation')
        self.assertEqual(revision_view['validationPolicies'][0]['status'],
                         'success')

    def test_show_revision_failed_validation_policy(self):
        # Simulate 4 document payload with an internally generated validation
        # policy which executes 'deckhand-schema-validation'.
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        validation_policy = self.factory.gen(types.DECKHAND_SCHEMA_VALIDATION,
                                             status='failed')
        payload.append(validation_policy)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)

        revision = self.show_revision(documents[0]['revision_id'])
        revision_view = self.view_builder.show(revision)

        expected_attrs = ('id', 'url', 'createdAt', 'validationPolicies',
                          'status')

        for attr in expected_attrs:
            self.assertIn(attr, revision_view)

        self.assertEqual('failed', revision_view['status'])
        self.assertIsInstance(revision_view['validationPolicies'], list)
        self.assertEqual(1, len(revision_view['validationPolicies']))
        self.assertEqual(revision_view['validationPolicies'][0]['name'],
                         'deckhand-schema-validation')
        self.assertEqual(revision_view['validationPolicies'][0]['status'],
                         'failed')
