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

import yaml

import falcon
import mock

from deckhand import policy
from deckhand.tests.unit.control import base as test_base


class TestErrorFormatting(test_base.BaseControllerTest):
    """Test suite for validating error formatting.

    Use mocked exceptions below to guarantee consistent results.
    """

    def test_base_exception_formatting(self):
        """Verify formatting for an exception class that inherits from
        :class:`Exception`.
        """
        with mock.patch.object(
                policy, '_do_enforce_rbac',
                spec_set=policy._do_enforce_rbac) as m_enforce_rbac:
            m_enforce_rbac.side_effect = Exception
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/test/documents',
                headers={'Content-Type': 'application/x-yaml'}, body=None)

        expected = {
            'status': 'Failure',
            'kind': 'status',
            'code': '500 Internal Server Error',
            'apiVersion': 'v1.0',
            'reason': '',
            'retry': True,
            'details': {
                'errorType': 'Exception',
                'errorCount': 1,
                'messageList': [
                    {
                        'message': 'An error occurred, but was not specified',
                        'error': True
                    }
                ]
            },
            'message': 'Unhandled Exception raised: ',
            'metadata': {}
        }
        body = yaml.safe_load(resp.text)

        self.assertEqual(500, resp.status_code)
        self.assertEqual(expected, body)

    def test_falcon_exception_formatting(self):
        """Verify formatting for an exception class that inherits from
        :class:`falcon.HTTPError`.
        """
        expected_msg = (
            'deckhand:create_cleartext_documents is disallowed by policy')

        with mock.patch.object(
                policy, '_do_enforce_rbac',
                spec_set=policy._do_enforce_rbac) as m_enforce_rbac:
            m_enforce_rbac.side_effect = falcon.HTTPForbidden(
                description=expected_msg)
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/test/documents',
                headers={'Content-Type': 'application/x-yaml'}, body=None)

        expected = {
            'status': 'Failure',
            'kind': 'status',
            'code': '403 Forbidden',
            'apiVersion': 'v1.0',
            'reason': '403 Forbidden',
            'retry': False,
            'details': {
                'errorType': 'HTTPForbidden',
                'errorCount': 1,
                'messageList': [
                    {
                        'message': expected_msg,
                        'error': True
                    }
                ]
            },
            'message': expected_msg,
            'metadata': {}
        }
        body = yaml.safe_load(resp.text)

        self.assertEqual(403, resp.status_code)
        self.assertEqual(expected, body)
