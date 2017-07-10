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

from oslo_serialization import jsonutils as json
import six

from deckhand.engine import secret_substitution
from deckhand import errors


class TestSecretSubtitution(testtools.TestCase):

    def setUp(self):
        super(TestSecretSubtitution, self).setUp()
        dir_path = os.path.dirname(os.path.realpath(__file__))
        test_yaml_path = os.path.abspath(os.path.join(
            dir_path, os.pardir, 'resources', 'sample.yaml'))

        with open(test_yaml_path, 'r') as yaml_file:
            yaml_data = yaml_file.read()
        self.data = yaml.safe_load(yaml_data)

    def _corrupt_data(self, key):
        corrupted_data = copy.deepcopy(self.data)

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

        return yaml.safe_dump(corrupted_data)

    def _format_data(self, data=None):
        if data is None:
            data = self.data
        return yaml.safe_dump(data)

    def test_initialization(self):
        sub = secret_substitution.SecretSubstitution(self._format_data())
        self.assertIsInstance(sub, secret_substitution.SecretSubstitution)

    def test_initialization_missing_sections(self):
        expected_err = ("The provided YAML file is invalid. Exception: '%s' "
                        "is a required property.")
        invalid_data = [
            (self._corrupt_data('data'), 'data'),
            (self._corrupt_data('metadata'), 'metadata'),
            (self._corrupt_data('metadata.name'), 'name'),
            (self._corrupt_data('metadata.storage'), 'storage'),
            (self._corrupt_data('metadata.substitutions'), 'substitutions'),
            (self._corrupt_data('metadata.substitutions.0.dest'), 'dest'),
            (self._corrupt_data('metadata.substitutions.0.src'), 'src')
        ]

        for invalid_entry, missing_key in invalid_data:
            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       expected_err % missing_key):
                secret_substitution.SecretSubstitution(invalid_entry)

    def test_initialization_bad_substitutions(self):
        expected_err = ('The attribute "%s" included in the "dest" field "%s" '
                        'is missing from the YAML data')
        invalid_data = []

        data = copy.deepcopy(self.data)
        data['metadata']['substitutions'][0]['dest'] = 'foo'
        invalid_data.append(self._format_data(data))

        data = copy.deepcopy(self.data)
        data['metadata']['substitutions'][0]['dest'] = 'tls_endpoint.bar'
        invalid_data.append(self._format_data(data))

        def _test(invalid_entry, field, dest):
            _expected_err = expected_err % (field, dest)
            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       _expected_err):
                secret_substitution.SecretSubstitution(invalid_entry)

        # Verify that invalid body dest reference is invalid.
        _test(invalid_data[0], "foo", "foo")
        # Verify that nested invalid body dest reference is invalid.
        _test(invalid_data[1], "bar", "tls_endpoint.bar")
