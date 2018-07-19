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

import os
import yaml

import falcon
import mock

from deckhand.common import document as document_wrapper
from deckhand import policy
from deckhand.tests.unit.control import base as test_base


class TestErrorFormatting(test_base.BaseControllerTest):
    """Test suite for validating error formatting."""

    def test_python_exception_formatting(self):
        """Verify formatting for an exception class that inherits from
        :class:`Exception`.
        """
        with mock.patch.object(
                policy, '_do_enforce_rbac',
                spec_set=policy._do_enforce_rbac) as m_enforce_rbac:
            m_enforce_rbac.side_effect = Exception('test error')
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/test/documents',
                headers={'Content-Type': 'application/x-yaml'}, body=None)

        expected = {
            'status': 'Failure',
            'kind': 'Status',
            'code': '500 Internal Server Error',
            'apiVersion': 'v1.0',
            'reason': 'Unspecified',
            'retry': True,
            'details': {
                'errorType': 'Exception',
                'errorCount': 1,
                'messageList': [
                    {
                        'message': 'Unhandled Exception raised: test error',
                        'error': True
                    }
                ]
            },
            'message': 'Unhandled Exception raised: test error',
            'metadata': {}
        }
        body = yaml.load(resp.text)

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
            'kind': 'Status',
            'code': '403 Forbidden',
            'apiVersion': 'v1.0',
            'reason': 'Unspecified',
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


class TestValidationMessageFormatting(test_base.BaseControllerTest):
    """Test suite for validating :class:`ValidationMessage` formatting."""

    def test_put_bucket_validation_message_formatting(self):
        """Verify formatting for pre-validation during updating a bucket."""
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/test/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body='foo: bar')

        expected = {
            'status': 'Failure',
            'kind': 'Status',
            'code': '400 Bad Request',
            'apiVersion': 'v1.0',
            'reason': 'Validation',
            'retry': False,
            'details': {
                'errorType': 'InvalidDocumentFormat',
                'errorCount': 2,
                'messageList': [
                    {
                        'diagnostic': mock.ANY,
                        'documents': [{
                            'layer': '',
                            'name': '',
                            'schema': ''
                        }],
                        'error': True,
                        'kind': 'ValidationMessage',
                        'level': 'Error',
                        'message': mock.ANY,
                        # Indicates sanity-check failure pre-rendering.
                        'name': 'D001'
                    },
                    {
                        'diagnostic': mock.ANY,
                        'documents': [{
                            'layer': '',
                            'name': '',
                            'schema': ''
                        }],
                        'error': True,
                        'kind': 'ValidationMessage',
                        'level': 'Error',
                        'message': mock.ANY,
                        'name': 'D001'
                    }
                ]
            },
            'message': 'The provided documents failed schema validation.',
            'metadata': {}
        }
        body = yaml.safe_load(resp.text)

        self.assertEqual(400, resp.status_code)
        self.assertEqual(expected, body)

    def test_rendered_documents_validation_message_formatting(self):
        """Verify formatting for post-validation during rendering revision
        documents.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        yaml_file = os.path.join(os.getcwd(), 'deckhand', 'tests', 'unit',
                                 'resources', 'sample_layering_policy.yaml')
        with open(yaml_file) as yaml_stream:
            payload = yaml_stream.read()

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/test/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=payload)

        with mock.patch('deckhand.control.revision_documents.db_api'
                        '.revision_documents_get', autospec=True) \
                as mock_get_rev_documents:
            invalid_document = document_wrapper.DocumentDict(
                yaml.safe_load(payload))
            invalid_document.pop('metadata')

            mock_get_rev_documents.return_value = [invalid_document]
            resp = self.app.simulate_get(
                '/api/v1.0/revisions/1/rendered-documents',
                headers={'Content-Type': 'application/x-yaml'})

        expected = {
            'status': 'Failure',
            'kind': 'Status',
            'code': '500 Internal Server Error',
            'apiVersion': 'v1.0',
            'reason': 'Validation',
            'retry': True,
            'details': {
                'errorType': 'InvalidDocumentFormat',
                'errorCount': 1,
                'messageList': [
                    {
                        'diagnostic': mock.ANY,
                        'documents': [{
                            'layer': '',
                            'name': '',
                            'schema': invalid_document['schema']
                        }],
                        'error': True,
                        'kind': 'ValidationMessage',
                        'level': 'Error',
                        'message': mock.ANY,
                        # Indicates sanity-check failure post-rendering.
                        'name': 'D001'
                    }
                ]
            },
            'message': 'The provided documents failed schema validation.',
            'metadata': {}
        }
        body = yaml.safe_load(resp.text)

        self.assertEqual(500, resp.status_code)
        self.assertEqual(expected, body)
