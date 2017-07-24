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

import jsonschema
from oslo_log import log as logging
import six

from deckhand.engine.schema.v1_0 import default_policy_validation
from deckhand.engine.schema.v1_0 import default_schema_validation
from deckhand import errors

LOG = logging.getLogger(__name__)


class DocumentValidation(object):
    """Class for document validation logic for YAML files.

    This class is responsible for performing built-in validations on Documents.

    :param data: YAML data that requires secrets to be validated, merged and
        consolidated.
    """

    def __init__(self, data):
        self.data = data
        self.pre_validate_data()

    class SchemaVersion(object):
        """Class for retrieving correct schema for pre-validation on YAML.

        Retrieves the schema that corresponds to "apiVersion" in the YAML
        data. This schema is responsible for performing pre-validation on
        YAML data.

        The built-in validation schemas that are always executed include:

          - `deckhand-document-schema-validation`
          - `deckhand-policy-validation`
        """

        # TODO: Use the correct validation based on the Document's schema.
        internal_validations = [
            {'version': 'v1', 'fqn': 'deckhand-document-schema-validation',
             'schema': default_schema_validation},
            {'version': 'v1', 'fqn': 'deckhand-policy-validation',
             'schema': default_policy_validation}]

        def __init__(self, schema_version):
            self.schema_version = schema_version

        @property
        def schema(self):
            # TODO: return schema based on Document's schema.
            return [v['schema'] for v in self.internal_validations
                    if v['version'] == self.schema_version][0].schema

    def pre_validate_data(self):
        """Pre-validate that the YAML file is correctly formatted."""
        self._validate_with_schema()

    def _validate_with_schema(self):
        # Validate the document using the document's ``schema``. Only validate
        # concrete documents.
        try:
            abstract = self.data['metadata']['layeringDefinition'][
                'abstract']
            is_abstract = six.text_type(abstract).lower() == 'true'
        except KeyError as e:
            raise errors.InvalidFormat(
                "Could not find 'abstract' property from document.")

        if is_abstract:
            LOG.info(
                "Skipping validation for the document because it is abstract")
            return

        try:
            schema_version = self.data['schema'].split('/')[-1]
            doc_schema_version = self.SchemaVersion(schema_version)
        except (AttributeError, IndexError, KeyError) as e:
            raise errors.InvalidFormat(
                'The provided schema is invalid or missing. Exception: '
                '%s.' % e)
        try:
            jsonschema.validate(self.data, doc_schema_version.schema)
        except jsonschema.exceptions.ValidationError as e:
            raise errors.InvalidFormat('The provided YAML file is invalid. '
                                       'Exception: %s.' % e.message)

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
