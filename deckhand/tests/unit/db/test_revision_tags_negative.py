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

from deckhand.db.sqlalchemy import api as db_api
from deckhand import errors
from deckhand.tests.unit import base


class TestRevisionTagsNegative(base.DeckhandWithDBTestCase):

    def test_create_tag_revision_not_found(self):
        self.assertRaises(
            errors.RevisionNotFound, db_api.revision_tag_create, -1)

    def test_show_tag_revision_not_found(self):
        self.assertRaises(
            errors.RevisionNotFound, db_api.revision_tag_get, -1)

    def test_delete_tag_revision_not_found(self):
        self.assertRaises(
            errors.RevisionNotFound, db_api.revision_tag_delete, -1)

    def test_list_tags_revision_not_found(self):
        self.assertRaises(
            errors.RevisionNotFound, db_api.revision_tag_get_all, -1)

    def test_delete_all_tags_revision_not_found(self):
        self.assertRaises(
            errors.RevisionNotFound, db_api.revision_tag_delete_all, -1)
