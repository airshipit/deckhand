# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from deckhand.tests.unit import base as test_base
from deckhand import utils


class TestUtils(test_base.DeckhandTestCase):

    def test_jsonpath_replace_creates_object(self):
        path = ".values.endpoints.admin"
        expected = {'values': {'endpoints': {'admin': 'foo'}}}
        result = utils.jsonpath_replace({}, 'foo', path)
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_array_index_creates_array(self):
        path = ".values.endpoints[0].admin"
        expected = {'values': {'endpoints': [{'admin': 'foo'}]}}
        result = utils.jsonpath_replace({}, 'foo', path)
        self.assertEqual(expected, result)

        path = ".values.endpoints[1].admin"
        expected = {'values': {'endpoints': [{}, {'admin': 'foo'}]}}
        result = utils.jsonpath_replace({}, 'foo', path)
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_numeric_value_creates_object(self):
        path = ".values.endpoints0.admin"
        expected = {'values': {'endpoints0': {'admin': 'foo'}}}
        result = utils.jsonpath_replace({}, 'foo', path)
        self.assertEqual(expected, result)
