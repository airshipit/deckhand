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

from deckhand.tests.unit.db import base


class TestRevisionViews(base.TestDbBase):

    def test_list(self):
        payload = [base.DocumentFixture.get_minimal_fixture()
                   for _ in range(4)]
        self._create_documents(payload)

        revisions = self._list_revisions()
        self.assertIsInstance(revisions, list)
        self.assertEqual(1, len(revisions))
        self.assertEqual(4, len(revisions[0]['documents']))
