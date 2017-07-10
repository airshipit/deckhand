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

import jsonschema

from deckhand import errors
from deckhand.engine.schema.v1_0 import default_schema


class SecretSubstitution(object):
    """Initialization of class for secret substitution logic for YAML files.

    This class is responsible for parsing, validating and retrieving secret
    values for values stored in the YAML file. Afterward, secret values will be
    substituted or "forward-repalced" into the YAML file. The end result is a
    YAML file containing all necessary secrets to be handed off to other
    services.
    """

    def __init__(self, data):
        try:
            self.data = yaml.safe_load(data)
        except yaml.YAMLError:
            raise errors.InvalidFormat(
                'The provided YAML file cannot be parsed.')

        self.validate_data()

    def validate_data(self):
        """Validate that the YAML file is correctly formatted.

        The YAML file must adhere to the following bare minimum format:

        .. code-block:: yaml

            ---
            apiVersion: service/v1
            kind: ConsumerOfCertificateData
            metadata:
              substitutions:
                - dest: .tls_endpoint.certificate
                  src:
                    apiVersion: deckhand/v1
                    kind: Certificate
                    name: some-certificate-asdf-1234
                # Forward-reference to specific section under "data" below.
                - dest: .tls_endpoint.certificateKey
                  src:
                    apiVersion: deckhand/v1
                    kind: CertificateKey
                    name: some-certificate-key-asdf-1234
            data:
              tls_endpoint:
                  certificate: null  # Data to be substituted.
                  certificateKey: null  # Data to be substituted.
        """
        try:
            jsonschema.validate(self.data, default_schema.schema)
        except jsonschema.exceptions.ValidationError as e:
            raise errors.InvalidFormat('The provided YAML file is invalid. '
                                       'Exception: %s.' % e.message)

        # Validate that each "dest" field exists in the YAML data.
        substitutions = self.data['metadata']['substitutions']
        destinations = [s['dest'] for s in substitutions]
        sub_data = self.data['data']

        for dest in destinations:
            result, missing_attr = self._multi_getattr(dest, sub_data)
            if not result:
                raise errors.InvalidFormat(
                    'The attribute "%s" included in the "dest" field "%s" is '
                    'missing from the YAML data: "%s".' % (
                        missing_attr, dest, sub_data))

    def _multi_getattr(self, multi_key, substitutable_data):
        """Iteratively check for nested attributes in the YAML data.

        Check for nested attributes included in "dest" attributes in the data
        section of the YAML file. For example, a "dest" attribute of
        ".foo.bar.baz" should mean that the YAML data adheres to:

        .. code-block:: yaml

           ---
           foo:
               bar:
                   baz: <data_to_be_substituted_here>

        :param multi_key: A multi-part key that references nested data in the
            substitutable part of the YAML data, e.g. ".foo.bar.baz".
        :param substitutable_data: The section of data in the YAML data that
            is intended to be substituted with secrets.
        :returns: Tuple where first value is a boolean indicating that the
            nested attribute was found and the second value is the attribute
            that was not found, if applicable.
        """
        attrs = multi_key.split('.')
        # Ignore the first attribute if it is "." as that is a self-reference.
        if attrs[0] == '':
            attrs = attrs[1:]

        data = substitutable_data
        for attr in attrs:
            if attr not in data:
                return False, attr
            data = data.get(attr)

        return True, None
