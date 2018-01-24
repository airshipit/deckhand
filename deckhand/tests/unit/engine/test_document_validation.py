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
from deckhand.tests.unit.engine import base as engine_test_base

from deckhand import factories
from deckhand import utils


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
            'metadata.layeringDefinition.actions',
            'metadata.layeringDefinition.parentSelector',
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
            test_document, True, 'metadata.layeringDefinition.abstract')
        document_validation.DocumentValidation(
            abstract_document).validate_all()
        self.assertTrue(mock_log.info.called)
        self.assertIn("Skipping schema validation for abstract document",
                      mock_log.info.mock_calls[0][1][0])

    @mock.patch.object(document_validation, 'jsonschema', autospec=True)
    def test_validation_failure_does_not_expose_secrets(self, mock_jsonschema):
        m_args = mock.Mock()
        mock_jsonschema.Draft4Validator(m_args).iter_errors.side_effect = [
            # Return empty list of errors for base schema validator and pretend
            # that 1 error is returned for next validator.
            [], [mock.Mock(path=[], schema_path=[])]
        ]
        test_document = self._read_data('sample_document')
        for sub in test_document['metadata']['substitutions']:
            substituted_data = utils.jsonpath_replace(
                test_document['data'], 'scary-secret', sub['dest']['path'])
            test_document['data'].update(substituted_data)
        self.assertEqual(
            'scary-secret', utils.jsonpath_parse(test_document['data'],
                                                 sub['dest']['path']))

        validations = document_validation.DocumentValidation(
            test_document).validate_all()

        self.assertEqual(2, len(validations[0]['errors']))
        self.assertIn('Sanitized to avoid exposing secret.',
                      str(validations[0]['errors'][-1]))
        self.assertNotIn('scary-secret.', str(validations[0]['errors'][-1]))
