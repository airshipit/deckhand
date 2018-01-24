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

import copy

from deckhand.db.sqlalchemy import api as db_api
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestRevisionDiffing(base.TestDbBase):

    def _verify_buckets_status(self, revision_id, comparison_revision_id,
                               expected):
        # Verify that actual and expected results match, despite the order of
        # `comparison_revision_id` and `revision_id` args.
        revision_ids = [revision_id, comparison_revision_id]
        for rev_ids in (revision_ids, reversed(revision_ids)):
            actual = db_api.revision_diff(*rev_ids)
            self.assertEqual(expected, actual)

    def test_revision_diff_null(self):
        self._verify_buckets_status(0, 0, {})

    def test_revision_diff_created(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)
        revision_id = documents[0]['revision_id']

        self._verify_buckets_status(
            0, revision_id, {bucket_name: 'created'})

    def test_revision_diff_multi_bucket_created(self):
        revision_ids = []
        bucket_names = []

        for _ in range(3):
            payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
            bucket_name = test_utils.rand_name('bucket')
            bucket_names.append(bucket_name)
            documents = self.create_documents(bucket_name, payload)
            revision_id = documents[0]['revision_id']
            revision_ids.append(revision_id)

        # Between revision 1 and 0, 1 bucket is created.
        self._verify_buckets_status(
            0, revision_ids[0], {b: 'created' for b in bucket_names[:1]})

        # Between revision 2 and 0, 2 buckets are created.
        self._verify_buckets_status(
            0, revision_ids[1], {b: 'created' for b in bucket_names[:2]})

        # Between revision 3 and 0, 3 buckets are created.
        self._verify_buckets_status(
            0, revision_ids[2], {b: 'created' for b in bucket_names})

    def test_revision_diff_self(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)
        revision_id = documents[0]['revision_id']

        self._verify_buckets_status(
            revision_id, revision_id, {bucket_name: 'unmodified'})

    def test_revision_diff_multi_bucket_self(self):
        bucket_names = []
        revision_ids = []

        for _ in range(3):
            payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
            bucket_name = test_utils.rand_name('bucket')
            # Store each bucket that was created.
            bucket_names.append(bucket_name)
            documents = self.create_documents(bucket_name, payload)
            # Store each revision that was created.
            revision_id = documents[0]['revision_id']
            revision_ids.append(revision_id)

        # The last revision should contain history for the previous 2 revisions
        # such that its diff history will show history for 3 buckets. Similarly
        # the 2nd revision will have history for 2 buckets and the 1st revision
        # for 1 bucket.
        # 1st revision has revision history for 1 bucket.
        self._verify_buckets_status(
            revision_ids[0], revision_ids[0], {bucket_names[0]: 'unmodified'})
        # 2nd revision has revision history for 2 buckets.
        self._verify_buckets_status(
            revision_ids[1], revision_ids[1],
            {b: 'unmodified' for b in bucket_names[:2]})
        # 3rd revision has revision history for 3 buckets.
        self._verify_buckets_status(
            revision_ids[2], revision_ids[2],
            {b: 'unmodified' for b in bucket_names})

    def test_revision_diff_modified(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        bucket_name = test_utils.rand_name('bucket')
        documents = self.create_documents(bucket_name, payload)
        revision_id = documents[0]['revision_id']

        payload[0]['data'] = {'modified': 'modified'}
        comparison_documents = self.create_documents(bucket_name, payload)
        comparison_revision_id = comparison_documents[0]['revision_id']

        self._verify_buckets_status(
            revision_id, comparison_revision_id, {bucket_name: 'modified'})

    def test_revision_diff_multi_revision_modified(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        bucket_name = test_utils.rand_name('bucket')
        revision_ids = []

        for _ in range(3):
            payload[0]['data'] = {'modified': test_utils.rand_name('modified')}
            documents = self.create_documents(bucket_name, payload)
            revision_id = documents[0]['revision_id']
            revision_ids.append(revision_id)

        for pair in [(0, 1), (0, 2), (1, 2)]:
            self._verify_buckets_status(
                revision_ids[pair[0]], revision_ids[pair[1]],
                {bucket_name: 'modified'})

    def test_revision_diff_multi_revision_multi_bucket_modified(self):
        revision_ids = []

        bucket_name = test_utils.rand_name('bucket')
        alt_bucket_name = test_utils.rand_name('bucket')
        bucket_names = [bucket_name, alt_bucket_name] * 2

        # Create revisions by modifying documents in `bucket_name` and
        # `alt_bucket_name`.
        for bucket_idx in range(4):
            payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
            documents = self.create_documents(
                bucket_names[bucket_idx], payload)
            revision_id = documents[0]['revision_id']
            revision_ids.append(revision_id)

        # Between revision_ids[0] and [1], bucket_name is unmodified and
        # alt_bucket_name is created.
        self._verify_buckets_status(
            revision_ids[0], revision_ids[1],
            {bucket_name: 'unmodified', alt_bucket_name: 'created'})

        # Between revision_ids[0] and [2], bucket_name is modified (by 2) and
        # alt_bucket_name is created (by 1).
        self._verify_buckets_status(
            revision_ids[0], revision_ids[2],
            {bucket_name: 'modified', alt_bucket_name: 'created'})

        # Between revision_ids[0] and [3], bucket_name is modified (by [2]) and
        # alt_bucket_name is created (by [1]) (as well as modified by [3]).
        self._verify_buckets_status(
            revision_ids[0], revision_ids[3],
            {bucket_name: 'modified', alt_bucket_name: 'created'})

        # Between revision_ids[1] and [2], bucket_name is modified but
        # alt_bucket_name remains unmodified.
        self._verify_buckets_status(
            revision_ids[1], revision_ids[2],
            {bucket_name: 'modified', alt_bucket_name: 'unmodified'})

        # Between revision_ids[1] and [3], bucket_name is modified (by [2]) and
        # alt_bucket_name is modified by [3].
        self._verify_buckets_status(
            revision_ids[1], revision_ids[3],
            {bucket_name: 'modified', alt_bucket_name: 'modified'})

        # Between revision_ids[2] and [3], alt_bucket_name is modified but
        # bucket_name remains unmodified.
        self._verify_buckets_status(
            revision_ids[2], revision_ids[3],
            {bucket_name: 'unmodified', alt_bucket_name: 'modified'})

    def test_revision_diff_ignore_bucket_with_unrelated_documents(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        alt_payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        alt_bucket_name = test_utils.rand_name('bucket')

        # Create a bucket with a single document.
        documents = self.create_documents(bucket_name, payload)
        revision_id = documents[0]['revision_id']

        # Create another bucket with an entirely different document (different
        # schema and metadata.name).
        self.create_documents(alt_bucket_name, alt_payload)

        # Modify the document from the 1st bucket.
        payload['data'] = {'modified': 'modified'}
        documents = self.create_documents(bucket_name, payload)
        comparison_revision_id = documents[0]['revision_id']

        # The `alt_bucket_name` should be created.
        self._verify_buckets_status(
            revision_id, comparison_revision_id,
            {bucket_name: 'modified', alt_bucket_name: 'created'})

    def test_revision_diff_ignore_bucket_with_all_unrelated_documents(self):
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=3)
        alt_payload = copy.deepcopy(payload)
        bucket_name = test_utils.rand_name('bucket')
        alt_bucket_name = test_utils.rand_name('bucket')

        # Create a bucket with 3 documents.
        documents = self.create_documents(bucket_name, payload)
        revision_id = documents[0]['revision_id']

        # Modify all 3 documents from first bucket.
        for idx in range(3):
            alt_payload[idx]['name'] = test_utils.rand_name('name')
            alt_payload[idx]['schema'] = test_utils.rand_name('schema')
        self.create_documents(
            alt_bucket_name, alt_payload)

        # Modify the document from the 1st bucket.
        payload[0]['data'] = {'modified': 'modified'}
        documents = self.create_documents(bucket_name, payload)
        comparison_revision_id = documents[0]['revision_id']

        # The alt_bucket_name should be created.
        self._verify_buckets_status(
            revision_id, comparison_revision_id,
            {bucket_name: 'modified', alt_bucket_name: 'created'})

    def test_revision_diff_deleted(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        revision_id = created_documents[0]['revision_id']

        # Delete the previously created document.
        deleted_documents = self.create_documents(bucket_name, [])
        comparison_revision_id = deleted_documents[0]['revision_id']

        self._verify_buckets_status(
            revision_id, comparison_revision_id, {bucket_name: 'deleted'})

    def test_revision_diff_delete_then_recreate(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        revision_id_1 = created_documents[0]['revision_id']

        # Delete the previously created document.
        deleted_documents = self.create_documents(bucket_name, [])
        revision_id_2 = deleted_documents[0]['revision_id']

        # Recreate the previously deleted document.
        recreated_documents = self.create_documents(bucket_name, payload)
        revision_id_3 = recreated_documents[0]['revision_id']

        # Verify that the revision for recreated document compared to revision
        # for deleted document is created, ignoring order.
        self._verify_buckets_status(
            revision_id_2, revision_id_3, {bucket_name: 'created'})

        # Verify that the revision for recreated document compared to revision
        # for created document is unmodified, ignoring order.
        self._verify_buckets_status(
            revision_id_1, revision_id_3, {bucket_name: 'unmodified'})

    def test_revision_diff_ignore_mistake_document(self):
        payload = base.DocumentFixture.get_minimal_fixture()
        bucket_name = test_utils.rand_name('first_bucket')
        created_documents = self.create_documents(bucket_name, payload)
        revision_id_1 = created_documents[0]['revision_id']

        # Create then delete an "accidental" document create request.
        alt_payload = base.DocumentFixture.get_minimal_fixture()
        alt_bucket_name = test_utils.rand_name('mistake_bucket')
        created_documents = self.create_documents(alt_bucket_name, alt_payload)
        revision_id_2 = created_documents[0]['revision_id']
        deleted_documents = self.create_documents(alt_bucket_name, [])
        revision_id_3 = deleted_documents[0]['revision_id']

        alt_payload_2 = base.DocumentFixture.get_minimal_fixture()
        alt_bucket_name_2 = test_utils.rand_name('second_bucket')
        created_documents = self.create_documents(
            alt_bucket_name_2, alt_payload_2)
        revision_id_4 = created_documents[0]['revision_id']

        self._verify_buckets_status(
            revision_id_1, revision_id_2, {bucket_name: 'unmodified',
                                           alt_bucket_name: 'created'})
        self._verify_buckets_status(
            revision_id_2, revision_id_3, {bucket_name: 'unmodified',
                                           alt_bucket_name: 'deleted'})
        self._verify_buckets_status(
            revision_id_1, revision_id_3, {bucket_name: 'unmodified'})
        # Should not contain information about `alt_bucket_name` as it was a
        # "mistake": created then deleted between the revisions in question.
        self._verify_buckets_status(
            revision_id_1, revision_id_4,
            {bucket_name: 'unmodified', alt_bucket_name_2: 'created'})
