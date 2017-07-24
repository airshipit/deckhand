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

import copy
import os
import testtools
import yaml

import mock
import six

from deckhand.engine import document_validation
from deckhand import errors


class TestDocumentValidation(testtools.TestCase):

    def setUp(self):
        super(TestDocumentValidation, self).setUp()
        dir_path = os.path.dirname(os.path.realpath(__file__))
        test_yaml_path = os.path.abspath(os.path.join(
            dir_path, os.pardir, 'resources', 'sample.yaml'))

        with open(test_yaml_path, 'r') as yaml_file:
            yaml_data = yaml_file.read()
        self.data = yaml.safe_load(yaml_data)

    def _corrupt_data(self, key, data=None):
        """Corrupt test data to check that pre-validation works.

        Corrupt data by removing a key from the document. Each key must
        correspond to a value that is a dictionary.

        :param key: The document key to be removed. The key can have the
            following formats:
                * 'data' => document.pop('data')
                * 'metadata.name' => document['metadata'].pop('name')
                * 'metadata.substitutions.0.dest' =>
                   document['metadata']['substitutions'][0].pop('dest')
        :returns: Corrupted data.
        """
        if data is None:
            data = self.data
        corrupted_data = copy.deepcopy(data)

        if '.' in key:
            _corrupted_data = corrupted_data
            nested_keys = key.split('.')
            for nested_key in nested_keys:
                if nested_key == nested_keys[-1]:
                    break
                if nested_key.isdigit():
                    _corrupted_data = _corrupted_data[int(nested_key)]
                else:
                    _corrupted_data = _corrupted_data[nested_key]
            _corrupted_data.pop(nested_keys[-1])
        else:
            corrupted_data.pop(key)

        return corrupted_data

    def test_initialization(self):
        doc_validation = document_validation.DocumentValidation(
            self.data)
        self.assertIsInstance(doc_validation,
                              document_validation.DocumentValidation)

    def test_initialization_missing_sections(self):
        expected_err = ("The provided YAML file is invalid. Exception: '%s' "
                        "is a required property.")
        invalid_data = [
            (self._corrupt_data('data'), 'data'),
            (self._corrupt_data('metadata.schema'), 'schema'),
            (self._corrupt_data('metadata.name'), 'name'),
            (self._corrupt_data('metadata.substitutions'), 'substitutions'),
            (self._corrupt_data('metadata.substitutions.0.dest'), 'dest'),
            (self._corrupt_data('metadata.substitutions.0.src'), 'src')
        ]

        for invalid_entry, missing_key in invalid_data:
            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       expected_err % missing_key):
                document_validation.DocumentValidation(invalid_entry)

    def test_initialization_missing_abstract_section(self):
        expected_err = ("Could not find 'abstract' property from document.")

        invalid_data = [
            self._corrupt_data('metadata'),
            self._corrupt_data('metadata.layeringDefinition'),
            self._corrupt_data('metadata.layeringDefinition.abstract'),
        ]

        for invalid_entry in invalid_data:
            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       expected_err):
                document_validation.DocumentValidation(invalid_entry)

    @mock.patch.object(document_validation, 'LOG', autospec=True)
    def test_initialization_with_abstract_document(self, mock_log):
        abstract_data = copy.deepcopy(self.data)

        for true_val in (True, 'true', 'True'):
            abstract_data['metadata']['layeringDefinition']['abstract'] = True

            document_validation.DocumentValidation(abstract_data)
            mock_log.info.assert_called_once_with(
                "Skipping validation for the document because it is abstract")
            mock_log.info.reset_mock()
