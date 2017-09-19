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


class TestRevisionRollbackNegative(base.TestDbBase):

    def test_rollback_same_revision_raises_error(self):
        # Revision 1: Create 4 documents.
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=4)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        orig_revision_id = created_documents[0]['revision_id']

        # Attempt to rollback to the latest revision, which should result
        # in an error.
        self.assertRaises(
            errors.InvalidRollback, self.rollback_revision, orig_revision_id)

    def test_rollback_unchanged_revision_history_raises_error(self):
        # Revision 1: Create 4 documents.
        payload = base.DocumentFixture.get_minimal_multi_fixture(count=4)
        bucket_name = test_utils.rand_name('bucket')
        created_documents = self.create_documents(bucket_name, payload)
        orig_revision_id = created_documents[0]['revision_id']

        # Create a 2nd revision that is a carbon-copy of 1st.
        self.create_documents(bucket_name, payload)

        # Attempt to rollback to the 1st revision, which should result in an
        # error, as it is identical to the latest revision.
        self.assertRaises(
            errors.InvalidRollback, self.rollback_revision, orig_revision_id)
