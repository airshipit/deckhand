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

from deckhand.tests.unit.control import base as test_base


class TestBucketsController(test_base.BaseControllerTest):
    """Test suite for validating positive scenarios bucket controller."""


class TestBucketsControllerNegative(test_base.BaseControllerTest):
    """Test suite for validating negative scenarios bucket controller."""

    def test_put_bucket_with_invalid_document_payload(self):
        no_colon_spaces = """
name:foo
schema:
    layeringDefinition:
        layer:site
"""
        invalid_payloads = ['garbage', no_colon_spaces]
        error_re = ['.*The provided YAML failed schema validation.*',
                    '.*mapping values are not allowed here.*']

        for idx, payload in enumerate(invalid_payloads):
            resp = self.app.simulate_put('/api/v1.0/bucket/mop/documents',
                                         body=payload)
            self.assertEqual(400, resp.status_code)
            self.assertRegexpMatches(resp.text, error_re[idx])
