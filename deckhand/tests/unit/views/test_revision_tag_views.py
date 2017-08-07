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

from deckhand.control.views import revision_tag
from deckhand.db.sqlalchemy import api as db_api
from deckhand.tests import test_utils
from deckhand.tests.unit.db import base


class TestRevisionViews(base.TestDbBase):

    def setUp(self):
        super(TestRevisionViews, self).setUp()
        self.view_builder = revision_tag.ViewBuilder()
        self.revision_id = self.create_revision()

    def test_revision_tag_show_view(self):
        rand_prefix = test_utils.rand_name(self.__class__.__name__)
        tag = rand_prefix + '-Tag'
        data_key = rand_prefix + '-Key'
        data_val = rand_prefix + '-Val'
        expected_view = {'tag': tag, 'data': {data_key: data_val}}

        created_tag = db_api.revision_tag_create(
            self.revision_id, tag, {data_key: data_val})

        actual_view = self.view_builder.show(created_tag)
        self.assertEqual(expected_view, actual_view)

    def test_revision_tag_list_view(self):
        expected_view = []

        # Create 2 revision tags for the same revision.
        for _ in range(2):
            rand_prefix = test_utils.rand_name(self.__class__.__name__)
            tag = rand_prefix + '-Tag'
            data_key = rand_prefix + '-Key'
            data_val = rand_prefix + '-Val'

            db_api.revision_tag_create(
                self.revision_id, tag, {data_key: data_val})

            expected_view.append({'tag': tag, 'data': {data_key: data_val}})

        retrieved_tags = db_api.revision_tag_get_all(self.revision_id)

        actual_view = self.view_builder.list(retrieved_tags)
        self.assertEqual(sorted(expected_view, key=lambda t: t['tag']),
                         actual_view)
