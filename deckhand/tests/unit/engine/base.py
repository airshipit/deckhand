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
import yaml

import mock
import six

from deckhand.engine import document_validation
from deckhand import errors
from deckhand.tests.unit import base as test_base


class TestDocumentValidationBase(test_base.DeckhandTestCase):

    def _read_data(self, file_name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        test_yaml_path = os.path.abspath(os.path.join(
            dir_path, os.pardir, 'resources', file_name + '.yaml'))

        with open(test_yaml_path, 'r') as yaml_file:
            yaml_data = yaml_file.read()
        self.data = yaml.safe_load(yaml_data)

    def _corrupt_data(self, key, value=None, data=None, op='delete'):
        """Corrupt test data to check that pre-validation works.

        Corrupt data by removing a key from the document (if ``op`` is delete)
        or by replacing the value corresponding to the key with ``value`` (if
        ``op`` is replace).

        :param key: The document key to be removed. The key can have the
            following formats:
                * 'data' => document.pop('data')
                * 'metadata.name' => document['metadata'].pop('name')
                * 'metadata.substitutions.0.dest' =>
                   document['metadata']['substitutions'][0].pop('dest')
        :type key: string
        :param value: The new value that corresponds to the (nested) document
            key (only used if ``op`` is 'replace').
        :type value: type string
        :param data: The data to "corrupt".
        :type data: dict
        :param op: Controls whether data is deleted (if "delete") or is
            replaced with ``value`` (if "replace").
        :type op: string
        :returns: Corrupted data.
        """
        if data is None:
            data = self.data
        if op not in ('delete', 'replace'):
            raise ValueError("The ``op`` argument must either be 'delete' or "
                             "'replace'.")
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
            if op == 'delete':
                _corrupted_data.pop(nested_keys[-1])
            elif op == 'replace':
                _corrupted_data[nested_keys[-1]] = value
        else:
            if op == 'delete':
                corrupted_data.pop(key)
            elif op == 'replace':
                corrupted_data[key] = value

        return corrupted_data
