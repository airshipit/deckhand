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


class TestDocumentValidation(engine_test_base.TestDocumentValidationBase):

    def test_init_document_validation(self):
        self._read_data('sample_document')
        doc_validation = document_validation.DocumentValidation(
            self.data)
        self.assertIsInstance(doc_validation,
                              document_validation.DocumentValidation)

    def test_data_schema_missing_optional_sections(self):
        self._read_data('sample_data_schema')
        optional_missing_data = [
            self._corrupt_data('metadata.labels'),
        ]

        for missing_data in optional_missing_data:
            document_validation.DocumentValidation(missing_data).validate_all()

    def test_document_missing_optional_sections(self):
        self._read_data('sample_document')
        properties_to_remove = (
            'metadata.layeringDefinition.actions',
            'metadata.layeringDefinition.parentSelector',
            'metadata.substitutions',
            'metadata.substitutions.2.dest.pattern')

        for property_to_remove in properties_to_remove:
            optional_data_removed = self._corrupt_data(property_to_remove)
            document_validation.DocumentValidation(
                optional_data_removed).validate_all()

    @mock.patch.object(document_validation, 'LOG', autospec=True)
    def test_abstract_document_not_validated(self, mock_log):
        self._read_data('sample_document')
        # Set the document to abstract.
        updated_data = self._corrupt_data(
            'metadata.layeringDefinition.abstract', True, op='replace')
        # Guarantee that a validation error is thrown by removing a required
        # property.
        del updated_data['metadata']['layeringDefinition']['layer']

        document_validation.DocumentValidation(updated_data).validate_all()
        self.assertTrue(mock_log.info.called)
        self.assertIn("Skipping schema validation for abstract document",
                      mock_log.info.mock_calls[0][1][0])
