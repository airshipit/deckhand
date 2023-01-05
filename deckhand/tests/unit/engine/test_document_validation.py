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

from unittest import mock

from deckhand.common import utils
from deckhand.engine import document_validation
from deckhand import factories
from deckhand.tests.unit.engine import base as engine_test_base


class TestDocumentValidation(engine_test_base.TestDocumentValidationBase):

    def setUp(self):
        super(TestDocumentValidation, self).setUp()
        self.test_document = self._read_data('sample_document')
        dataschema_factory = factories.DataSchemaFactory()
        self.dataschema = dataschema_factory.gen_test(
            self.test_document['schema'], {})

    def test_data_schema_missing_optional_sections(self):
        optional_missing_data = [
            self._corrupt_data(self.test_document, 'metadata.labels'),
        ]

        for missing_data in optional_missing_data:
            payload = [missing_data, self.dataschema]
            document_validation.DocumentValidation(payload).validate_all()

    def test_document_missing_optional_sections(self):
        properties_to_remove = (
            'metadata.substitutions',
            'metadata.substitutions.2.dest.pattern')

        for property_to_remove in properties_to_remove:
            missing_data = self._corrupt_data(self.test_document,
                                              property_to_remove)
            payload = [missing_data, self.dataschema]
            document_validation.DocumentValidation(payload).validate_all()

    @mock.patch.object(document_validation, 'LOG', autospec=True)
    def test_abstract_document_not_validated(self, mock_log):
        test_document = self._read_data('sample_passphrase')
        # Set the document to abstract.
        abstract_document = utils.jsonpath_replace(
            test_document, True, '.metadata.layeringDefinition.abstract')
        document_validation.DocumentValidation(
            abstract_document, pre_validate=False).validate_all()
        self.assertTrue(mock_log.info.called)
        self.assertIn("Skipping schema validation for abstract document",
                      mock_log.info.mock_calls[0][1][0])

    @mock.patch.object(document_validation, 'jsonschema', autospec=True)
    def test_validation_failure_sanitizes_error_section_secrets(
            self, mock_jsonschema):
        mock_jsonschema.Draft4Validator = mock.Mock()
        mock_jsonschema.Draft4Validator().iter_errors.side_effect = [
            # Return empty list of errors for base schema and metadata
            # validator and pretend that 1 error is returned for next
            # validator.
            [],
            [],
            [mock.Mock(path=[], schema_path=[], message='scary-secret-here')]
        ]

        document_factory = factories.DocumentFactory(1, [1])
        test_document = document_factory.gen_test(
            {
                '_GLOBAL_DATA_1_': {'data': {'secret-a': 5}},
                '_GLOBAL_SUBSTITUTIONS_1_': [
                    {'src': {
                        'path': '.', 'schema': 'foo/bar/v1', 'name': 'foo'},
                     'dest': {'path': '.secret-a'}}
                ]
            },
            global_abstract=False)[-1]

        data_schema_factory = factories.DataSchemaFactory()
        data_schema = data_schema_factory.gen_test(test_document['schema'], {})

        validations = document_validation.DocumentValidation(
            test_document, existing_data_schemas=[data_schema],
            pre_validate=False).validate_all()

        self.assertEqual(1, len(validations[0]['errors']))
        self.assertIn('Sanitized to avoid exposing secret.',
                      str(validations[0]['errors'][-1]))
        self.assertNotIn('scary-secret.', str(validations[0]['errors'][-1]))

    def test_validation_document_duplication(self):
        """Validate that duplicate document fails when duplicate passed in."""
        test_document = self._read_data('sample_document')

        # Should only fail when pre_validate is True as the `db` module already
        # handles this on behalf of the controller.
        validations = document_validation.DocumentValidation(
            [test_document] * 2,  # Provide 2 of the same document.
            pre_validate=True).validate_all()

        expected_error = {
            'diagnostic': mock.ANY,
            'documents': [{
                'layer': test_document['metadata']['layeringDefinition'][
                    'layer'],
                'name': test_document['metadata']['name'],
                'schema': test_document['schema']
            }],
            'error': True,
            'kind': 'ValidationMessage',
            'level': 'Error',
            'message': 'Duplicate document exists',
            'name': 'Deckhand validation error'
        }

        self.assertEqual(1, len(validations[1]['errors']))
        self.assertEqual(expected_error,
                         validations[1]['errors'][0])

        # With pre_validate=False the validation should skip.
        validations = document_validation.DocumentValidation(
            [test_document] * 2,  # Provide 2 of the same document.
            pre_validate=False).validate_all()
        self.assertEmpty(validations[1]['errors'])

    def test_validation_failure_sanitizes_message_secrets(self):
        data_schema_factory = factories.DataSchemaFactory()
        metadata_name = 'example/Doc/v1'
        schema_to_use = {
            '$schema': 'http://json-schema.org/schema#',
            'type': 'object',
            'properties': {
                'secret-a': {'type': 'string'}
            },
            'required': ['secret-a'],
            'additionalProperties': False
        }
        data_schema = data_schema_factory.gen_test(
            metadata_name, data=schema_to_use)

        # Case 1: Check that sensitive data is sanitized if the document has
        # substitutions and `metadata.storagePolicy` == 'cleartext'.
        document_factory = factories.DocumentFactory(1, [1])
        test_document = document_factory.gen_test({
            "_GLOBAL_DATA_1_": {'data': {'secret-a': 5}},
            "_GLOBAL_SCHEMA_1_": metadata_name,
            "_GLOBAL_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".secret-a"
                },
                "src": {
                    "schema": "deckhand/CertificateKey/v1",
                    "name": "site-cert",
                    "path": "."
                }
            }],
        }, global_abstract=False)[-1]
        test_document['metadata']['storagePolicy'] = 'cleartext'

        validations = document_validation.DocumentValidation(
            test_document, existing_data_schemas=[data_schema],
            pre_validate=False).validate_all()

        self.assertEqual(1, len(validations[0]['errors']))
        self.assertEqual('Sanitized to avoid exposing secret.',
                         validations[0]['errors'][0]['message'])

        # Case 2: Check that sensitive data is sanitized if the document has
        # no substitutions and `metadata.storagePolicy` == 'encrypted'.
        test_document = document_factory.gen_test({
            "_GLOBAL_DATA_1_": {'data': {'secret-a': 5}},
            "_GLOBAL_SCHEMA_1_": metadata_name,
            "_GLOBAL_SUBSTITUTIONS_1_": [],
        }, global_abstract=False)[-1]
        test_document['metadata']['storagePolicy'] = 'encrypted'

        validations = document_validation.DocumentValidation(
            test_document, existing_data_schemas=[data_schema],
            pre_validate=False).validate_all()

        self.assertEqual(1, len(validations[0]['errors']))
        self.assertEqual('Sanitized to avoid exposing secret.',
                         validations[0]['errors'][0]['message'])

    def test_parent_selector_and_actions_both_provided_is_valid(self):
        test_document = self._read_data('sample_document')
        data_schema_factory = factories.DataSchemaFactory()
        data_schema = data_schema_factory.gen_test(test_document['schema'], {})

        validations = document_validation.DocumentValidation(
            test_document, existing_data_schemas=[data_schema],
            pre_validate=False).validate_all()

        self.assertEmpty(validations[0]['errors'])

    def test_neither_parent_selector_nor_actions_provided_is_valid(self):
        test_document = self._read_data('sample_document')
        test_document['metadata']['layeringDefinition'].pop('actions')
        test_document['metadata']['layeringDefinition'].pop('parentSelector')

        data_schema_factory = factories.DataSchemaFactory()
        data_schema = data_schema_factory.gen_test(test_document['schema'], {})

        validations = document_validation.DocumentValidation(
            test_document, existing_data_schemas=[data_schema],
            pre_validate=False).validate_all()

        self.assertEmpty(validations[0]['errors'])
