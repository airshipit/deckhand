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

from unittest import mock

from deckhand import factories
from deckhand.tests.unit.control import base as test_base


class TestYAMLTranslator(test_base.BaseControllerTest):

    def test_request_with_correct_content_type(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(1, [1])
        document = documents_factory.gen_test({})[-1]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump(document),
        )
        self.assertEqual(200, resp.status_code)

    def test_request_empty_put_and_content_type(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            headers={'Content-Type': 'application/x-yaml'},
        )
        self.assertEqual(200, resp.status_code)

    def test_request_empty_put_and_no_content_type(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
        )
        self.assertEqual(200, resp.status_code)

    def test_request_zero_length_put_and_no_content_type(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            body='',
        )
        self.assertEqual(200, resp.status_code)

    def test_request_zero_length_put_and_content_type(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body='',
        )
        self.assertEqual(200, resp.status_code)

    def test_request_with_no_content_type_on_get(self):
        resp = self.app.simulate_get(
            '/versions',
            headers={})
        self.assertEqual(200, resp.status_code)

    def test_request_with_superfluous_content_type_on_get(self):
        resp = self.app.simulate_get(
            '/versions',
            headers={'Content-Type': 'application/x-yaml'},
        )
        self.assertEqual(200, resp.status_code)

    def test_request_with_correct_content_type_plus_encoding(self):
        rules = {'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(1, [1])
        document = documents_factory.gen_test({})[-1]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            headers={'Content-Type': 'application/x-yaml;encoding=utf-8'},
            body=yaml.safe_dump(document),
        )
        self.assertEqual(200, resp.status_code)


class TestYAMLTranslatorNegative(test_base.BaseControllerTest):

    def test_request_without_content_type_raises_exception(self):
        self._read_data('sample_document_simple')
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            body=yaml.safe_dump(self.data),
        )
        self.assertEqual(400, resp.status_code)

        expected = {
            'apiVersion': mock.ANY,
            'code': '400 Bad Request',
            'details': {
                'errorCount': 1,
                'errorType': 'HTTPMissingHeader',
                'messageList': [{
                    'error': True,
                    'message': "The \"Content-Type\" header is required."
                }]
            },
            'kind': 'Status',
            'message': "The \"Content-Type\" header is required.",
            'metadata': {},
            'reason': 'Unspecified',
            'retry': False,
            'status': 'Failure'
        }

        self.assertEqual(expected, yaml.safe_load(resp.content))

    def test_request_with_invalid_content_type_raises_exception(self):
        self._read_data('sample_document_simple')
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            headers={'Content-Type': 'application/json'},
            body=yaml.safe_dump(self.data),
        )

        self.assertEqual(415, resp.status_code)

        expected = {
            'apiVersion': mock.ANY,
            'code': '415 Unsupported Media Type',
            'details': {
                'errorCount': 1,
                'errorType': 'HTTPUnsupportedMediaType',
                'messageList': [{
                    'error': True,
                    'message': (
                        "Unexpected content type: application/json. Expected "
                        "content types are: ['application/x-yaml'].")
                }]
            },
            'kind': 'Status',
            'message': ("Unexpected content type: application/json. Expected "
                        "content types are: ['application/x-yaml']."),
            'metadata': {},
            'reason': 'Unspecified',
            'retry': False,
            'status': 'Failure'
        }
        self.assertEqual(expected, yaml.safe_load(resp.content))

    def test_request_with_invalid_yaml_content_type_raises_exception(self):
        """Only application/x-yaml should be supported, not application/yaml,
        because it hasn't been registered as an official MIME type yet.
        """
        self._read_data('sample_document_simple')
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/b1/documents',
            headers={'Content-Type': 'application/yaml'},
            body=yaml.safe_dump(self.data),
        )
        self.assertEqual(415, resp.status_code)

        expected = {
            'apiVersion': mock.ANY,
            'code': '415 Unsupported Media Type',
            'details': {
                'errorCount': 1,
                'errorType': 'HTTPUnsupportedMediaType',
                'messageList': [{
                    'error': True,
                    'message': (
                        "Unexpected content type: application/yaml. Expected "
                        "content types are: ['application/x-yaml'].")
                }]
            },
            'kind': 'Status',
            'message': ("Unexpected content type: application/yaml. Expected "
                        "content types are: ['application/x-yaml']."),
            'metadata': {},
            'reason': 'Unspecified',
            'retry': False,
            'status': 'Failure'
        }
        self.assertEqual(expected, yaml.safe_load(resp.content))
