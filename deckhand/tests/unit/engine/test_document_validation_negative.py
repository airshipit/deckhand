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

import mock

from deckhand.engine import document_validation
from deckhand import errors
from deckhand.tests.unit.engine import base as test_base
from deckhand import types


class TestDocumentValidationNegative(test_base.TestDocumentValidationBase):
    """Negative testing suite for document validation."""

    BASIC_PROPERTIES = (
        'metadata',
        'metadata.schema',
        'metadata.name',
        'metadata.layeringDefinition',
        'metadata.layeringDefinition.layer',
        'schema'
    )

    CRITICAL_PROPERTIES = (
        'schema',
        'metadata',
        'metadata.schema',
        'metadata.name',
        'metadata.substitutions.0.dest',
        'metadata.substitutions.0.dest.path',
        'metadata.substitutions.0.src',
        'metadata.substitutions.0.src.schema',
        'metadata.substitutions.0.src.name',
        'metadata.substitutions.0.src.path'
    )

    def _do_validations(self, document_validator, expected, expected_err):
        validations = document_validator.validate_all()

        self.assertEqual(1, len(validations))
        self.assertEqual('failure', validations[-1]['status'])
        self.assertEqual({'version': '1.0', 'name': 'deckhand'},
                         validations[-1]['validator'])
        self.assertEqual(types.DECKHAND_SCHEMA_VALIDATION,
                         validations[-1]['name'])
        self.assertEqual(1, len(validations[-1]['errors']))

        for key in ('name', 'schema', 'path', 'error_section',
                    'validation_schema', 'schema_path', 'message'):
            self.assertIn(key, validations[-1]['errors'][-1])

        self.assertEqual(expected['metadata']['name'],
                         validations[-1]['errors'][-1]['name'])
        self.assertEqual(expected['schema'],
                         validations[-1]['errors'][-1]['schema'])
        self.assertEqual(expected_err,
                         validations[-1]['errors'][-1]['message'])

    def _test_missing_required_sections(self, document, properties_to_remove):
        for idx, property_to_remove in enumerate(properties_to_remove):
            missing_prop = property_to_remove.split('.')[-1]
            invalid_data = self._corrupt_data(document, property_to_remove)

            exception_raised = property_to_remove in self.CRITICAL_PROPERTIES
            expected_err_msg = "'%s' is a required property" % missing_prop

            payload = [invalid_data]
            doc_validator = document_validation.DocumentValidation(
                payload, pre_validate=False)
            if exception_raised:
                self.assertRaises(
                    errors.InvalidDocumentFormat, doc_validator.validate_all)
            else:
                self._do_validations(doc_validator, invalid_data,
                                     expected_err_msg)

    def test_certificate_authority_key_missing_required_sections(self):
        document = self._read_data('sample_certificate_authority_key')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_certificate_authority_missing_required_sections(self):
        document = self._read_data('sample_certificate_authority')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_certificate_key_missing_required_sections(self):
        document = self._read_data('sample_certificate_key')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_certificate_missing_required_sections(self):
        document = self._read_data('sample_certificate')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_data_schema_missing_required_sections(self):
        properties_to_remove = (
            'metadata',
            'metadata.schema',
            'metadata.name',
            'schema',
            'data.$schema'
        )
        document = self._read_data('sample_data_schema')
        self._test_missing_required_sections(document, properties_to_remove)

    def test_generic_document_missing_required_sections(self):
        document = self._read_data('sample_document')
        properties_to_remove = self.CRITICAL_PROPERTIES
        self._test_missing_required_sections(document, properties_to_remove)

    def test_generic_document_missing_multiple_required_sections(self):
        """Validates that multiple errors are reported for a document with
        multiple validation errors.
        """
        document = self._read_data('sample_document')
        properties_to_remove = (
            'metadata.layeringDefinition.actions.0.method',
            'metadata.layeringDefinition.actions.0.path',
            'metadata.substitutions.0.dest.path',
            'metadata.substitutions.0.src.name',
            'metadata.substitutions.0.src.path',
            'metadata.substitutions.0.src.schema',
        )
        for property_to_remove in properties_to_remove:
            document = self._corrupt_data(document, property_to_remove)

        doc_validator = document_validation.DocumentValidation(document)
        e = self.assertRaises(errors.InvalidDocumentFormat,
                              doc_validator.validate_all)

        for idx, property_to_remove in enumerate(properties_to_remove):
            parts = property_to_remove.split('.')
            missing_property = parts[-1]

            expected_err = "'%s' is a required property" % missing_property
            self.assertIn(expected_err, e.message)

    def test_document_invalid_layering_definition_action(self):
        document = self._read_data('sample_document')
        missing_data = self._corrupt_data(
            document, 'metadata.layeringDefinition.actions.0.method',
            'invalid', op='replace')
        expected_err = (
            r".+ 'invalid' is not one of \['replace', 'delete', 'merge'\]")

        payload = [missing_data]
        doc_validator = document_validation.DocumentValidation(payload)
        self.assertRaisesRegexp(errors.InvalidDocumentFormat, expected_err,
                                doc_validator.validate_all)

    def test_layering_policy_missing_required_sections(self):
        properties_to_remove = (
            'metadata',
            'metadata.schema',
            'metadata.name',
            'schema',
            'data.layerOrder'
        )
        document = self._read_data('sample_layering_policy')
        self._test_missing_required_sections(document, properties_to_remove)

    def test_passphrase_missing_required_sections(self):
        document = self._read_data('sample_passphrase')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_privatekey_missing_required_sections(self):
        document = self._read_data('sample_private_key')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_publickey_missing_required_sections(self):
        document = self._read_data('sample_public_key')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'metadata.storagePolicy',)
        self._test_missing_required_sections(document, properties_to_remove)

    def test_validation_policy_missing_required_sections(self):
        document = self._read_data('sample_validation_policy')
        properties_to_remove = tuple(self.BASIC_PROPERTIES) + (
            'data.validations', 'data.validations.0.name')
        self._test_missing_required_sections(document, properties_to_remove)

    @mock.patch.object(document_validation, 'LOG', autospec=True)
    def test_invalid_document_schema_generates_error(self, mock_log):
        document = self._read_data('sample_document')
        document['schema'] = 'foo/bar/v1'

        doc_validator = document_validation.DocumentValidation(document)
        doc_validator.validate_all()
        self.assertRegex(
            mock_log.info.mock_calls[0][1][0],
            'The provided document schema %s is not registered.'
            % document['schema'])

    @mock.patch.object(document_validation, 'LOG', autospec=True)
    def test_invalid_document_schema_version_generates_error(self, mock_log):
        document = self._read_data('sample_passphrase')
        document['schema'] = 'deckhand/Passphrase/v5'

        doc_validator = document_validation.DocumentValidation(document)
        doc_validator.validate_all()
        self.assertRegex(
            mock_log.info.mock_calls[0][1][0],
            'The provided document schema %s is not registered.'
            % document['schema'])

    def test_invalid_validation_schema_raises_runtime_error(self):
        document = self._read_data('sample_passphrase')

        # Validate that broken built-in base schema raises RuntimeError.
        doc_validator = document_validation.DocumentValidation(document)
        doc_validator._validators[0].base_schema = 'fake'
        with self.assertRaisesRegexp(RuntimeError, 'Unknown error'):
            doc_validator.validate_all()

        # Validate that broken data schema for ``DataSchemaValidator`` raises
        # RuntimeError.
        document = self._read_data('sample_document')
        data_schema = self._read_data('sample_data_schema')
        data_schema['metadata']['name'] = document['schema']
        data_schema['data'] = 'fake'
        doc_validator = document_validation.DocumentValidation(
            [document, data_schema], pre_validate=False)
        with self.assertRaisesRegexp(RuntimeError, 'Unknown error'):
            doc_validator.validate_all()

    def test_parent_selector_but_no_actions_raises_validation_error(self):
        # Verify that an error is thrown if parentSelector is specified but
        # actions is missing altogether.
        document = self._read_data('sample_document')
        document['metadata']['layeringDefinition']['parentSelector'] = {
            'some': 'label'
        }
        document['metadata']['layeringDefinition'].pop('actions')
        doc_validator = document_validation.DocumentValidation(
            [document], pre_validate=False)
        self.assertRaises(
            errors.InvalidDocumentFormat, doc_validator.validate_all)

        # Verify that an error is thrown if parentSelector is specified but
        # at least 1 action isn't specified.
        document['metadata']['layeringDefinition']['actions'] = []
        doc_validator = document_validation.DocumentValidation(
            [document], pre_validate=False)
        self.assertRaises(
            errors.InvalidDocumentFormat, doc_validator.validate_all)

    def test_actions_but_no_parent_selector_raises_validation_error(self):
        # Verify that an error is thrown if actions are specified but
        # parentSelector is missing altogether.
        document = self._read_data('sample_document')
        document['metadata']['layeringDefinition'].pop('parentSelector')
        doc_validator = document_validation.DocumentValidation(
            [document], pre_validate=False)
        self.assertRaises(
            errors.InvalidDocumentFormat, doc_validator.validate_all)

        # Verify that an error is thrown if actions are specified but no
        # parentSelector labels are.
        document['metadata']['layeringDefinition']['parentSelector'] = {}
        doc_validator = document_validation.DocumentValidation(
            [document], pre_validate=False)
        self.assertRaises(
            errors.InvalidDocumentFormat, doc_validator.validate_all)
