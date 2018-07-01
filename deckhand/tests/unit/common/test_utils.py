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

import jsonpath_ng
import mock

from testtools.matchers import Equals
from testtools.matchers import MatchesAny

from deckhand.common import utils
from deckhand.tests.unit import base as test_base


class TestJSONPathReplace(test_base.DeckhandTestCase):
    """Validate that JSONPath replace function works."""

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


class TestJSONPathUtilsCaching(test_base.DeckhandTestCase):
    """Validate that JSONPath caching works."""

    def setUp(self):
        super(TestJSONPathUtilsCaching, self).setUp()
        self.jsonpath_call_count = 0

        def fake_parse(value):
            self.jsonpath_call_count += 1
            return jsonpath_ng.parse(value)

        self.fake_jsonpath_ng = fake_parse

    def test_jsonpath_parse_replace_cache(self):
        """Validate caching for both parsing and replacing functions."""
        path = ".values.endpoints.admin"
        expected = {'values': {'endpoints': {'admin': 'foo'}}}

        # Mock jsonpath_ng to return a monkey-patched parse function that
        # keeps track of call count and yet calls the actual function.
        with mock.patch.object(utils, 'jsonpath_ng',  # noqa: H210
                               parse=self.fake_jsonpath_ng):
            # Though this is called 3 times, the cached function should only
            # be called once, with the cache returning the cached value early.
            for _ in range(3):
                result = utils.jsonpath_replace({}, 'foo', path)
                self.assertEqual(expected, result)

            # Though this is called 3 times, the cached function should only
            # be called once, with the cache returning the cached value early.
            for _ in range(3):
                result = utils.jsonpath_parse(expected, path)
                self.assertEqual('foo', result)

        # Assert that the actual function was called <= 1 times. (Allow for 0
        # in case CI jobs clash.)
        self.assertThat(
            self.jsonpath_call_count, MatchesAny(Equals(0), Equals(1)))
