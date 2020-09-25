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

import hashlib
import jsonpath_ng
import mock

from oslo_serialization import jsonutils as json
from testtools.matchers import Equals
from testtools.matchers import MatchesAny

from deckhand.common import utils
from deckhand import errors
from deckhand import factories
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

    def test_jsonpath_replace_with_pattern(self):
        path = ".values.endpoints.admin"
        body = {"values": {"endpoints": {"admin": "REGEX_FRESH"}}}
        expected = {"values": {"endpoints": {"admin": "EAT_FRESH"}}}
        result = utils.jsonpath_replace(body, "EAT", jsonpath=path,
                                        pattern="REGEX")
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_and_array_index(self):
        path = ".values.endpoints.admin[1]"
        body = {"values": {"endpoints": {"admin": [None, "REGEX_FRESH"]}}}
        expected = {"values": {"endpoints": {"admin": [None, "EAT_FRESH"]}}}
        result = utils.jsonpath_replace(body, "EAT", jsonpath=path,
                                        pattern="REGEX")
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_recursive_dict(self):
        path = ".values"
        body = {"values": {"re1": "REGEX_ONE", "re2": "REGEX_TWO"}}
        expected = {"values": {"re1": "YES_ONE", "re2": "YES_TWO"}}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_recursive_list(self):
        path = ".values"

        # String entries inside list.
        body = {"values": ["REGEX_ONE", "REGEX_TWO"]}
        expected = {"values": ["YES_ONE", "YES_TWO"]}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

        # Dictionary entries inside list.
        body = {"values": [{"re1": "REGEX_ONE", "re2": "REGEX_TWO"}]}
        expected = {"values": [{"re1": "YES_ONE", "re2": "YES_TWO"}]}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_recursive_str(self):
        """Edge case to validate that passing in a path that leads to a string
        value itself (not a list or dict) still results in pattern replacement
        gracefully passing, even though no recursion is technically possible.
        """
        path = ".values.endpoints.admin"
        body = {"values": {"endpoints": {"admin": "REGEX_FRESH"}}}
        expected = {"values": {"endpoints": {"admin": "EAT_FRESH"}}}
        result = utils.jsonpath_replace(body, "EAT", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_recursive_dict_nested(self):
        path = ".values"
        body = {"values": {"re1": "REGEX_ONE", "nested": {"re2": "REGEX_TWO"}}}
        expected = {"values": {"re1": "YES_ONE", "nested": {"re2": "YES_TWO"}}}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_recursive_list_nested(self):
        path = ".values"

        # String entry inside nested list.
        body = {"values": [{"re1": "REGEX_ONE", "nested": ["REGEX_TWO"]}]}
        expected = {"values": [{"re1": "YES_ONE", "nested": ["YES_TWO"]}]}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

        # Dictionary entry inside nested list.
        body = {"values": [{"nested": [{"re2": "REGEX_TWO"}]}]}
        expected = {"values": [{"nested": [{"re2": "YES_TWO"}]}]}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_pattern_recursive_root_path(self):
        """Validate that recursion happens even from root path."""
        path = "$"
        body = {"values": {"re1": "REGEX_ONE", "nested": {"re2": "REGEX_TWO"}}}
        expected = {"values": {"re1": "YES_ONE", "nested": {"re2": "YES_TWO"}}}
        result = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                        pattern="REGEX", recurse={'depth': -1})
        self.assertEqual(expected, result)

    def test_jsonpath_replace_with_different_patterns_recursive(self):
        """Edge case to validate that different regexes that live recursively
        under the same parent path are handled gracefully. Note that
        non-matching regexes are obviously skipped over.
        """
        path = ".values"

        # Only the first string's pattern will be replaced since it'll match
        # REGEX. The second one won't as its pattern is XEGER.
        body = {"values": [{"re1": "REGEX_ONE", "nested": ["XEGER_TWO"]}]}
        expected = {"values": [{"re1": "YES_ONE", "nested": ["XEGER_TWO"]}]}
        result1 = utils.jsonpath_replace(body, "YES", jsonpath=path,
                                         pattern="REGEX",
                                         recurse={'depth': -1})
        self.assertEqual(expected, result1)

        # Now replace the second one by passing in pattern="XEGER".
        expected = {"values": [{"re1": "YES_ONE", "nested": ["NO_TWO"]}]}
        result2 = utils.jsonpath_replace(result1, "NO", jsonpath=path,
                                         pattern="XEGER",
                                         recurse={'depth': -1})
        self.assertEqual(expected, result2)

    def test_jsonpath_replace_with_recursion_depth_specified(self):
        # Only the first string's pattern will be replaced since it'll
        # only recurse 1 level.
        body = {"re1": "REGEX_ONE", "values": {"re2": "REGEX_TWO"}}
        expected = {"re1": "YES_ONE", "values": {"re2": "REGEX_TWO"}}
        result = utils.jsonpath_replace(body, "YES", jsonpath="$",
                                        pattern="REGEX",
                                        recurse={'depth': 1})
        self.assertEqual(expected, result)

        # Depth of 2 should cover both.
        body = {"re1": "REGEX_ONE", "values": {"re2": "REGEX_TWO"}}
        expected = {"re1": "YES_ONE", "values": {"re2": "YES_TWO"}}
        result = utils.jsonpath_replace(body, "YES", jsonpath="$",
                                        pattern="REGEX",
                                        recurse={'depth': 2})
        self.assertEqual(expected, result)

        # Depth of 3 is required as the list around "REGEX_TWO" results in
        # another layer of recursion.
        body = {"re1": "REGEX_ONE", "values": {"re2": ["REGEX_TWO"]}}
        expected = {"re1": "YES_ONE", "values": {"re2": ["YES_TWO"]}}
        result = utils.jsonpath_replace(body, "YES", jsonpath="$",
                                        pattern="REGEX",
                                        recurse={'depth': 3})
        self.assertEqual(expected, result)


class TestJSONPathReplaceNegative(test_base.DeckhandTestCase):
    """Validate JSONPath replace negative scenarios."""

    def test_jsonpath_replace_without_expected_pattern_raises_exc(self):
        empty_body = {}
        error_re = (".*missing the pattern %s specified under .* at path %s.*")

        self.assertRaisesRegex(errors.MissingDocumentPattern,
                               error_re % ("way invalid", r"\$.path"),
                               utils.jsonpath_replace,
                               empty_body,
                               value="test",
                               jsonpath=".path",
                               pattern="way invalid")


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


class TestRedactDocuments(test_base.DeckhandTestCase):
    """Validate Redact function works"""

    def test_redact_rendered_document(self):

        self.factory = factories.DocumentSecretFactory()
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "deckhand/Certificate/v1",
                    "name": "global-cert",
                    "path": "."
                }
            }]
        }
        data = mapping['_GLOBAL_DATA_1_']['data']
        doc_factory = factories.DocumentFactory(1, [1])
        document = doc_factory.gen_test(
            mapping, global_abstract=False)[-1]
        document['metadata']['storagePolicy'] = 'encrypted'

        with mock.patch.object(hashlib, 'sha256', autospec=True,
                               return_value=mock.sentinel.redacted)\
                as mock_sha256:
            redacted = mock.MagicMock()
            mock_sha256.return_value = redacted
            redacted.hexdigest.return_value = json.dumps(data)
            mock.sentinel.redacted = redacted.hexdigest.return_value
            redacted_doc = utils.redact_document(document)

        self.assertEqual(mock.sentinel.redacted, redacted_doc['data'])
        self.assertEqual(mock.sentinel.redacted,
                         redacted_doc['metadata']['substitutions'][0]
                         ['src']['path'])
        self.assertEqual(mock.sentinel.redacted,
                         redacted_doc['metadata']['substitutions'][0]
                         ['dest']['path'])
