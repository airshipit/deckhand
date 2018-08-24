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


class TestRevisionRollback(base.TestDbBase):

    def test_create_update_rollback(self):
        # Revision 1: Create 4 documents.
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=4)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        orig_revision_id = created_documents[0]['revision_id']

        # Revision 2: Update the last document.
        payload[-1]['data'] = {'foo': 'bar'}
        self.create_documents(bucket_name, payload)

        # Revision 3: rollback to revision 1.
        rollback_revision = self.rollback_revision(orig_revision_id)

        self.assertEqual(3, rollback_revision['id'])
        self.assertEqual(
            [1, 1, 1, 3],
            [d['revision_id'] for d in rollback_revision['documents']])
        self.assertEqual(
            [1, 1, 1, 3],
            [d['orig_revision_id'] for d in rollback_revision['documents']])

        rollback_documents = self.list_revision_documents(
            rollback_revision['id'])
        rollback_documents = sorted(rollback_documents,
                                    key=lambda d: d['created_at'])
        self.assertEqual([1, 1, 1, 3],
                         [d['revision_id'] for d in rollback_documents])
        self.assertEqual([1, 1, 1, 3],
                         [d['orig_revision_id'] for d in rollback_documents])

    def test_create_update_delete_rollback(self):
        # Revision 1: Create 4 documents.
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=4)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        orig_revision_id = created_documents[0]['revision_id']

        # Revision 2: Update the last document.
        payload[-1]['data'] = {'foo': 'bar'}
        self.create_documents(bucket_name, payload)

        # Revision 3: Delete the third document.
        payload.pop(2)
        self.create_documents(bucket_name, payload)

        # Rollback 4: rollback to revision 1.
        rollback_revision = self.rollback_revision(orig_revision_id)

        self.assertEqual(4, rollback_revision['id'])
        self.assertEqual(
            [1, 1, 4, 4],
            [d['revision_id'] for d in rollback_revision['documents']])
        self.assertEqual(
            [1, 1, 4, 4],
            [d['orig_revision_id'] for d in rollback_revision['documents']])

        rollback_documents = self.list_revision_documents(
            rollback_revision['id'])
        rollback_documents = sorted(rollback_documents,
                                    key=lambda d: d['created_at'])
        self.assertEqual([1, 1, 4, 4],
                         [d['revision_id'] for d in rollback_documents])
        self.assertEqual([1, 1, 4, 4],
                         [d['orig_revision_id'] for d in rollback_documents])

    def test_rollback_to_revision_same_as_current_revision(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=4)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        orig_revision_id = created_documents[0]['revision_id']
        orig_documents = self.list_revision_documents(orig_revision_id)

        rollback_revision = self.rollback_revision(orig_revision_id)
        self.assertDictItemsAlmostEqual(
            sorted(orig_documents, key=lambda d: d['created_at']),
            sorted(rollback_revision['documents'],
                   key=lambda d: d['created_at']),
            ignore=['created_at', 'updated_at', 'revision_id',
                    'orig_revision_id', 'id'])

    def test_rollback_to_revision_0_creates_blank_slate(self):
        """Rolling back to revision 0 should create an empty revision."""
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=4)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        orig_revision_id = created_documents[0]['revision_id']

        rollback_revision = self.rollback_revision(0)
        rollback_documents = self.list_revision_documents(
            rollback_revision['id'], include_history=False)
        self.assertEqual(orig_revision_id + 1, rollback_revision['id'])
        self.assertEmpty(rollback_documents)

    def test_rollback_to_revision_0_with_empty_revision_history(self):
        """Validate that rolling back to revision_id 0 should work with
        an empty revision history (zero existing revisions in the DB).
        """
        rollback_revision = self.rollback_revision(0)
        rollback_documents = self.list_revision_documents(
            rollback_revision['id'], include_history=False)
        self.assertEqual(1, rollback_revision['id'])
        self.assertEmpty(rollback_documents)


class TestRevisionRollbackNegative(base.TestDbBase):

    def test_rollback_to_missing_revision_raises_exc(self):
        # revision_id=1 doesn't exist yet since we start from an empty DB.
        self.assertRaises(errors.RevisionNotFound, self.rollback_revision, 1)
