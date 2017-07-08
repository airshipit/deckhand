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
import testtools

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

        with open(test_yaml_path, 'r') as yaml_data:
            self.yaml_data = yaml_data.read()

    def test_initialization_missing_substitutions_section(self):
        expected_err = (
            "The provided YAML file has no metadata/substitutions section")
        invalid_data = [
            {"data": []},
            {"data": [], "metadata": None},
            {"data": [], "metadata": {"missing_substitutions": None}}
        ]

        for invalid_entry in invalid_data:
            invalid_entry = json.dumps(invalid_entry)
            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       expected_err):
                secret_substitution.SecretSubstitution(invalid_entry)

        expected_err = (
            "The provided YAML file has no metadata/substitutions section")
        invalid_data = [
            {"data": [], "metadata": None},
        ]

    def test_initialization_missing_data_section(self):
        expected_err = (
            "The provided YAML file has no data section")
        invalid_data = '{"metadata": {"substitutions": []}}'

        with six.assertRaisesRegex(self, errors.InvalidFormat, expected_err):
            secret_substitution.SecretSubstitution(invalid_data)
        
    def test_initialization_missing_src_dest_sections(self):
        expected_err = ('The provided YAML file is missing the "%s" field for '
                        'the %s substition.')
        invalid_data = [
            {"data": [], "metadata": {"substitutions": [{"dest": "foo"}]}},
            {"data": [], "metadata": {"substitutions": [{"src": "bar"}]}},
        ]

        def _test(invalid_entry, field, substitution):
            invalid_entry = json.dumps(invalid_entry)
            _expected_err = expected_err % (field, substitution)

            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       _expected_err):
                secret_substitution.SecretSubstitution(invalid_entry)

        _test(invalid_data[0], "src", {"dest": "foo"})
        _test(invalid_data[1], "dest", {"src": "bar"})

    def test_initialization_bad_substitutions(self):
        expected_err = ('The attribute "%s" included in the "dest" field "%s" '
                        'is missing from the YAML data: "%s".')
        invalid_data = [
            # Missing attribute.
            {"data": {}, "metadata": {"substitutions": [
                {"src": "", "dest": "foo"}
            ]}},
            # Missing attribute.
            {"data": {"foo": None}, "metadata": {"substitutions": [
                {"src": "", "dest": "bar"}
            ]}},
            # Missing nested attribute.
            {"data": {"foo": {"baz": None}}, "metadata": {"substitutions": [
                {"src": "", "dest": "foo.bar"}
            ]}},
        ]

        def _test(invalid_entry, field, dest, substitution):
            invalid_entry = json.dumps(invalid_entry)
            _expected_err = expected_err % (field, dest, substitution)

            with six.assertRaisesRegex(self, errors.InvalidFormat,
                                       _expected_err):
                secret_substitution.SecretSubstitution(invalid_entry)

        _test(invalid_data[0], "foo", "foo", {})
        _test(invalid_data[1], "bar", "bar", {"foo": None})
        _test(invalid_data[2], "bar", "foo.bar", {'foo': {'baz': None}})
