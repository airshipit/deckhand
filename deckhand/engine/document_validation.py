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

from deckhand.engine.schema import base_schema
from deckhand.engine.schema import v1_0
from deckhand import errors
from deckhand import factories
from deckhand import types

LOG = logging.getLogger(__name__)


class DocumentValidation(object):
    """Class for document validation logic for YAML files.

    This class is responsible for validating YAML files according to their
    schema.

    :param documents: Documents to be validated.
    :type documents: List of dictionaries or dictionary.
    """

    def __init__(self, documents):
        if not isinstance(documents, (list, tuple)):
            documents = [documents]

        self.documents = documents

    class SchemaType(object):
        """Class for retrieving correct schema for pre-validation on YAML.

        Retrieves the schema that corresponds to "apiVersion" in the YAML
        data. This schema is responsible for performing pre-validation on
        YAML data.
        """

        # TODO(fmontei): Support dynamically registered schemas.
        schema_versions_info = [
            {'id': 'deckhand/CertificateKey',
             'schema': v1_0.certificate_key_schema},
            {'id': 'deckhand/Certificate',
             'schema': v1_0.certificate_schema},
            {'id': 'deckhand/DataSchema',
             'schema': v1_0.data_schema},
            # NOTE(fmontei): Fall back to the metadata's schema for validating
            # generic documents.
            {'id': 'metadata/Document',
             'schema': v1_0.document_schema},
            {'id': 'deckhand/LayeringPolicy',
             'schema': v1_0.layering_schema},
            {'id': 'deckhand/Passphrase',
             'schema': v1_0.passphrase_schema},
            {'id': 'deckhand/ValidationPolicy',
             'schema': v1_0.validation_schema}]

        def __init__(self, data):
            """Constructor for ``SchemaType``.

            Retrieve the relevant schema based on the API version and schema
            name contained in `document.schema` where `document` constitutes a
            single document in a YAML payload.

            :param api_version: The API version used for schema validation.
            :param schema: The schema property in `document.schema`.
            """
            self.schema = self.get_schema(data)

        def get_schema(self, data):
            # Fall back to `document.metadata.schema` if the schema cannot be
            # determined from `data.schema`.
            for doc_property in [data['schema'], data['metadata']['schema']]:
                schema = self._get_schema_by_property(doc_property)
                if schema:
                    return schema
            return None

        def _get_schema_by_property(self, doc_property):
            schema_parts = doc_property.split('/')
            doc_schema_identifier = '/'.join(schema_parts[:-1])

            for schema in self.schema_versions_info:
                if doc_schema_identifier == schema['id']:
                    return schema['schema'].schema
            return None

    def validate_all(self):
        """Pre-validate that the YAML file is correctly formatted.

        All concrete documents in the revision successfully pass their JSON
        schema validations. The result of the validation is stored under
        the "deckhand-document-schema-validation" validation namespace for
        a document revision.

        Validation is broken up into 2 stages:

            1) Validate that each document contains the basic bulding blocks
               needed: "schema", "metadata" and "data" using a "base" schema.
            2) Validate each specific document type (e.g. validation policy)
               using a more detailed schema.

        :returns: Dictionary mapping with keys being the unique name for each
            document and values being the validations executed for that
            document, including failed and succeeded validations.
        """
        internal_validation_docs = []
        validation_policy_factory = factories.ValidationPolicyFactory()

        for document in self.documents:
            document_validations = self._validate_one(document)

        deckhand_schema_validation = validation_policy_factory.gen(
            types.DECKHAND_SCHEMA_VALIDATION, status='success')
        internal_validation_docs.append(deckhand_schema_validation)

        return internal_validation_docs

    def _validate_one(self, document):
        # Subject every document to basic validation to verify that each
        # main section is present (schema, metadata, data).
        try:
            jsonschema.validate(document, base_schema.schema)
        except jsonschema.exceptions.ValidationError as e:
            raise errors.InvalidDocumentFormat(
                detail=e.message, schema=e.schema)

        doc_schema_type = self.SchemaType(document)
        if doc_schema_type.schema is None:
            raise errors.UknownDocumentFormat(
                document_type=document['schema'])

        # Perform more detailed validation on each document depending on
        # its schema. If the document is abstract, validation errors are
        # ignored.
        try:
            jsonschema.validate(document, doc_schema_type.schema)
        except jsonschema.exceptions.ValidationError as e:
            # TODO(fmontei): Use the `Document` object wrapper instead
            # once other PR is merged.
            if not self._is_abstract(document):
                raise errors.InvalidDocumentFormat(
                    detail=e.message, schema=e.schema,
                    document_type=document['schema'])
            else:
                LOG.info('Skipping schema validation for abstract '
                         'document: %s.' % document)

    def _is_abstract(self, document):
        try:
            is_abstract = document['metadata']['layeringDefinition'][
                'abstract'] == True
            return is_abstract
        # NOTE(fmontei): If the document is of ``document_schema`` type and
        # no "layeringDefinition" or "abstract" property is found, then treat
        # this as a validation error.
        except KeyError:
            doc_schema_type = self.SchemaType(document)
            return doc_schema_type is v1_0.document_schema
        return False
