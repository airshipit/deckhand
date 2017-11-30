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
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base
from deckhand import types


class TestRevisions(base.TestDbBase):

    def test_list(self):
        documents = [base.DocumentFixture.get_minimal_fixture()
                     for _ in range(4)]
        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, documents)

        revisions = self.list_revisions()
        self.assertIsInstance(revisions, list)
        self.assertEqual(1, len(revisions))
        self.assertEqual(4, len(revisions[0]['documents']))

    def test_create_many_update_one(self):
        documents = [base.DocumentFixture.get_minimal_fixture()
                     for _ in range(4)]
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, documents)
        orig_revision_id = created_documents[0]['revision_id']

        # Update the last document.
        documents[-1]['data'] = {'foo': 'bar'}
        updated_documents = self.create_documents(
            bucket_name, documents)
        new_revision_id = updated_documents[0]['revision_id']

        # 4 documents should be returned: the updated doc along with the other
        # 3 documents (unchanged) that accompanied the PUT request.
        self.assertEqual(4, len(updated_documents))
        self.assertEqual(created_documents[-1]['bucket_id'],
                         updated_documents[0]['bucket_id'])
        self.assertNotEqual(created_documents[-1]['revision_id'],
                            updated_documents[0]['revision_id'])

        revision_documents = self.list_revision_documents(
            updated_documents[0]['revision_id'])
        revision_documents = sorted(revision_documents,
                                    key=lambda d: d['created_at'])
        self.assertEqual(4, len(revision_documents))

        self.assertEqual([orig_revision_id] * 3 + [new_revision_id],
                         [d['revision_id'] for d in revision_documents])

        self.assertEqual(
            [(d['name'], d['schema'])
             for d in (created_documents[:-1] + [updated_documents[-1]])],
            [(d['name'], d['schema']) for d in revision_documents])

    def test_recreate_with_no_changes(self):
        # Verify that showing and listing revisions returns the revisions
        # with the original revision ID. This is because nothing has changed
        # so the "new" revision is just a carry-over from the original one.
        documents = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, documents)
        recreated_documents = self.create_documents(bucket_name, documents)

        created_rev_id = created_documents[0].pop('revision_id')
        recreated_rev_id = recreated_documents[0].pop('revision_id')
        recreated_orig_rev_id = recreated_documents[0].pop('orig_revision_id')

        for attr in ('data', 'metadata', 'name', 'schema'):
            self.assertEqual(
                created_documents[0][attr], recreated_documents[0][attr])
        self.assertEqual(created_rev_id, recreated_orig_rev_id)
        self.assertEqual(created_rev_id + 1, recreated_rev_id)

        # Verify that correct revision ID is returned for listing
        # revision documents.
        revision_documents = self.list_revision_documents(recreated_rev_id)
        docs_rev_id = revision_documents[0].pop('revision_id')

        for attr in ('data', 'metadata', 'name', 'schema'):
            self.assertEqual(
                revision_documents[0][attr], recreated_documents[0][attr])

        self.assertEqual(recreated_orig_rev_id, docs_rev_id)
        self.assertEqual(recreated_rev_id, docs_rev_id + 1)

        # Verify that each doc in revision['documents'] for listing revisions
        # has correct revision_id.
        retrieved_revisions = self.list_revisions()
        for rev in retrieved_revisions:
            self.assertEqual(created_rev_id,
                             rev['documents'][0]['revision_id'])

        # Verify that each doc in revision['documents'] for showing revision
        # details has correct revision_id.
        retrieved_revision = self.show_revision(recreated_rev_id)
        self.assertEqual(created_rev_id,
                         retrieved_revision['documents'][0]['revision_id'])

    def test_list_with_validation_policies(self):
        documents = [base.DocumentFixture.get_minimal_fixture()
                     for _ in range(4)]
        vp_factory = factories.ValidationPolicyFactory()
        validation_policy = vp_factory.gen(types.DECKHAND_SCHEMA_VALIDATION,
                                           'success')
        documents.extend([validation_policy])

        bucket_name = test_utils.rand_name('bucket')
        self.create_documents(bucket_name, documents)

        revisions = self.list_revisions()
        self.assertIsInstance(revisions, list)
        self.assertEqual(1, len(revisions))
        self.assertEqual(5, len(revisions[0]['documents']))
        self.assertEqual(types.VALIDATION_POLICY_SCHEMA,
                         revisions[0]['documents'][-1]['schema'])

    def test_delete_all(self):
        all_created_documents = []
        all_revision_ids = []

        for _ in range(3):
            document_payload = [base.DocumentFixture.get_minimal_fixture()]
            bucket_name = test_utils.rand_name('bucket')
            created_documents = self.create_documents(
                bucket_name, document_payload)
            all_created_documents.extend(created_documents)
            revision_id = created_documents[0]['revision_id']
            all_revision_ids.append(revision_id)

        self.delete_revisions()

        # Validate that all revisions were deleted.
        for revision_id in all_revision_ids:
            error_re = 'The requested revision %s was not found.' % revision_id
            self.assertRaisesRegex(errors.RevisionNotFound, error_re,
                                   self.show_revision, revision_id)

        # Validate that the documents (children) were deleted.
        for doc in created_documents:
            filters = {'id': doc['id']}
            error_re = 'The requested document %s was not found.' % filters
            self.assertRaisesRegex(errors.DocumentNotFound, error_re,
                                   self.show_document, **filters)

        # Validate that the revision/document ID was reset back to 1.
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(
            bucket_name, [base.DocumentFixture.get_minimal_fixture()])
        self.assertEqual(1, created_documents[0]['revision_id'])
        self.assertEqual(1, created_documents[0]['id'])

    def test_revision_history_multiple_buckets(self):
        documents = base.DocumentFixture.get_minimal_fixture()
        alt_documents = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        alt_bucket_name = test_utils.rand_name('bucket')

        created_documents = self.create_documents(bucket_name, documents)
        alt_created_documents = self.create_documents(
            alt_bucket_name, alt_documents)

        alt_revision_docs = self.list_revision_documents(
            alt_created_documents[0]['revision_id'])
        alt_revision_docs = sorted(alt_revision_docs,
                                   key=lambda d: d['created_at'])
        self.assertEqual(2, len(alt_revision_docs))

        expected_doc_ids = [created_documents[0]['id'],
                            alt_created_documents[0]['id']]
        self.assertEqual(
            expected_doc_ids, [d['id'] for d in alt_revision_docs])
