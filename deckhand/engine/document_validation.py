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

import abc
import re

import jsonschema
from oslo_log import log as logging
import six

from deckhand.engine import document_wrapper
from deckhand.engine.schema import base_schema
from deckhand.engine.schema import v1_0
from deckhand.engine.secrets_manager import SecretsSubstitution
from deckhand import errors
from deckhand import types
from deckhand import utils

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseValidator(object):
    """Abstract base validator.

    Sub-classes should override this to implement schema-specific document
    validation.
    """

    _supported_versions = ('v1',)
    _schema_re = re.compile(r'^[a-zA-Z]+\/[a-zA-Z]+\/v\d+(.0)?$')

    @abc.abstractmethod
    def matches(self, document):
        """Whether this Validator should be used to validate ``document``.

        :param dict document: Document to validate.
        :returns: True if Validator applies to ``document``, else False.
        """

    @abc.abstractmethod
    def validate(self, document):
        """Validate whether ``document`` passes schema validation."""


class GenericValidator(BaseValidator):
    """Validator used for validating all documents, regardless whether concrete
    or abstract, or what version its schema is.
    """

    def matches(self, document):
        # Applies to all schemas, so unconditionally returns True.
        return True

    def validate(self, document):
        """Validate ``document``against basic schema validation.

        Sanity-checks each document for mandatory keys like "metadata" and
        "schema".

        Applies even to abstract documents, as they must be consumed by
        concrete documents, so basic formatting is mandatory.

        Failure to pass this check results in an error.

        :param dict document: Document to validate.
        :raises RuntimeError: If the Deckhand schema itself is invalid.
        :raises errors.InvalidDocumentFormat: If the document failed schema
            validation.
        :returns: None

        """
        try:
            jsonschema.Draft4Validator.check_schema(base_schema.schema)
            schema_validator = jsonschema.Draft4Validator(base_schema.schema)
            error_messages = [
                e.message for e in schema_validator.iter_errors(document)]
        except Exception as e:
            raise RuntimeError(
                'Unknown error occurred while attempting to use Deckhand '
                'schema. Details: %s' % six.text_type(e))
        else:
            if error_messages:
                LOG.error(
                    'Failed sanity-check validation for document [%s] %s. '
                    'Details: %s', document.get('schema', 'N/A'),
                    document.get('metadata', {}).get('name'), error_messages)
                raise errors.InvalidDocumentFormat(details=error_messages)


class SchemaValidator(BaseValidator):
    """Validator for validating built-in document kinds."""

    _schema_map = {
        'v1': {
            'deckhand/CertificateAuthorityKey':
                    v1_0.certificate_authority_key_schema,
            'deckhand/CertificateAuthority': v1_0.certificate_authority_schema,
            'deckhand/CertificateKey': v1_0.certificate_key_schema,
            'deckhand/Certificate': v1_0.certificate_schema,
            'deckhand/DataSchema': v1_0.data_schema_schema,
            'deckhand/LayeringPolicy': v1_0.layering_policy_schema,
            'deckhand/Passphrase': v1_0.passphrase_schema,
            'deckhand/PrivateKey': v1_0.private_key_schema,
            'deckhand/PublicKey': v1_0.public_key_schema,
            'deckhand/ValidationPolicy': v1_0.validation_policy_schema,
        }
    }

    # Represents a generic document schema.
    _fallback_schema = v1_0.document_schema

    def _get_schemas(self, document):
        """Retrieve the relevant schemas based on the document's
        ``schema``.

        :param dict doc: The document used for finding the correct schema
            to validate it based on its ``schema``.
        :returns: A schema to be used by ``jsonschema`` for document
            validation.
        :rtype: dict

        """
        schema_prefix, schema_version = _get_schema_parts(document)
        matching_schemas = []
        relevant_schemas = self._schema_map.get(schema_version, {})
        for candidae_schema_prefix, schema in relevant_schemas.items():
            if candidae_schema_prefix == schema_prefix:
                if schema not in matching_schemas:
                    matching_schemas.append(schema)
        return matching_schemas

    def matches(self, document):
        if document.is_abstract:
            LOG.info('Skipping schema validation for abstract document [%s]: '
                     '%s.', document.schema, document.name)
            return False
        return True

    def validate(self, document, validate_section='',
                 use_fallback_schema=True):
        """Validate ``document`` against built-in ``schema``-specific schemas.

        Does not apply to abstract documents.

        :param dict document: Document to validate.
        :param str validate_section: Document section to validate. If empty
            string, validates entire ``document``.
        :param bool use_fallback_schema: Whether to use the "fallback" schema
            if no matching schemas are found by :method:``matches``.

        :raises RuntimeError: If the Deckhand schema itself is invalid.
        :returns: Tuple of (error message, parent path for failing property)
            following schema validation failure.
        :rtype: Generator[Tuple[str, str]]

        """
        schemas_to_use = self._get_schemas(document)
        if not schemas_to_use and use_fallback_schema:
            LOG.debug('Document schema %s not recognized. Using "fallback" '
                      'schema.', document.schema)
            schemas_to_use = [SchemaValidator._fallback_schema]

        for schema_to_use in schemas_to_use:
            schema = schema_to_use.schema
            if validate_section:
                to_validate = document.get(validate_section, None)
                root_path = '.' + validate_section + '.'
            else:
                to_validate = document
                root_path = '.'
            try:
                jsonschema.Draft4Validator.check_schema(schema)
                schema_validator = jsonschema.Draft4Validator(schema)
                errors = schema_validator.iter_errors(to_validate)
            except Exception as e:
                LOG.exception(six.text_type(e))
                raise RuntimeError(
                    'Unknown error occurred while attempting to use schema '
                    'for validation. Details: %s.' % six.text_type(e))
            else:
                for error in errors:
                    LOG.error(
                        'Failed schema validation for document [%s] %s. '
                        'Details: %s.', document.schema, document.name,
                        error.message)
                    yield _generate_validation_error_output(
                        schema_to_use, document, error, root_path)


class DataSchemaValidator(SchemaValidator):
    """Validator for validating ``DataSchema`` documents."""

    def __init__(self, data_schemas):
        super(DataSchemaValidator, self).__init__()
        self._schema_map = self._build_schema_map(data_schemas)

    def _build_schema_map(self, data_schemas):
        schema_map = {k: {} for k in self._supported_versions}

        for data_schema in data_schemas:
            # Ensure that each `DataSchema` document has required properties
            # before they themselves can be used to validate other documents.
            if 'name' not in data_schema.metadata:
                continue
            if self._schema_re.match(data_schema.name) is None:
                continue
            if 'data' not in data_schema:
                continue
            schema_prefix, schema_version = _get_schema_parts(data_schema,
                                                             'metadata.name')

            class Schema(object):
                schema = data_schema.data

            schema_map[schema_version].setdefault(schema_prefix, Schema())

        return schema_map

    def matches(self, document):
        if document.is_abstract:
            LOG.info('Skipping schema validation for abstract document [%s]: '
                     '%s.', document.schema, document.name)
            return False
        schema_prefix, schema_version = _get_schema_parts(document)
        return schema_prefix in self._schema_map.get(schema_version, {})

    def validate(self, document):
        return super(DataSchemaValidator, self).validate(
            document, validate_section='data', use_fallback_schema=False)


class DocumentValidation(object):

    def __init__(self, documents, existing_data_schemas=None):
        """Class for document validation logic for documents.

        This class is responsible for validating documents according to their
        schema.

        ``DataSchema`` documents must be validated first, as they are in turn
        used to validate other documents.

        :param documents: Documents to be validated.
        :type documents: List[dict]
        :param existing_data_schemas: ``DataSchema`` documents created in prior
            revisions to be used the "data" section of each document in
            ``documents``. Additional ``DataSchema`` documents in ``documents``
            are combined with these.
        :type existing_data_schemas: dict or List[dict]
        """

        self.documents = []
        existing_data_schemas = existing_data_schemas or []
        data_schemas = [document_wrapper.DocumentDict(d)
                        for d in existing_data_schemas]
        _data_schema_map = {d.name: d for d in data_schemas}

        if not isinstance(documents, list):
            documents = [documents]
        for document in documents:
            if not isinstance(document, document_wrapper.DocumentDict):
                document = document_wrapper.DocumentDict(document)
            if document.schema.startswith(types.DATA_SCHEMA_SCHEMA):
                data_schemas.append(document)
                # If a newer version of the same DataSchema was passed in,
                # only use the new one and discard the old one.
                if document.name in _data_schema_map:
                    data_schemas.remove(_data_schema_map.pop(document.name))
            self.documents.append(document)

        # NOTE(fmontei): The order of the validators is important. The
        # ``GenericValidator`` must come first.
        self._validators = [
            GenericValidator(),
            SchemaValidator(),
            DataSchemaValidator(data_schemas)
        ]

    def _get_supported_schema_list(self):
        schema_list = []
        for validator in self._validators[1:]:
            for schema_version, schema_map in validator._schema_map.items():
                for schema_prefix in schema_map:
                    schema_list.append(schema_prefix + '/' + schema_version)
        return schema_list

    def _format_validation_results(self, results):
        """Format the validation result to be compatible with database
        formatting.

        :results: The validation results generated during document validation.
        :type results: List[dict]
        :returns: List of formatted validation results.
        :rtype: List[dict]

        """
        internal_validator = {
            'name': 'deckhand',
            'version': '1.0'
        }

        formatted_results = []
        for result in results:
            formatted_result = {
                'name': types.DECKHAND_SCHEMA_VALIDATION,
                'status': result['status'],
                'validator': internal_validator,
                'errors': result['errors']
            }
            formatted_results.append(formatted_result)

        return formatted_results

    def _validate_one(self, document):
        result = {'errors': []}

        supported_schema_list = self._get_supported_schema_list()
        document_schema = None if not document.get('schema') else '/'.join(
            _get_schema_parts(document))
        if document_schema not in supported_schema_list:
            error_msg = ("The provided document schema %s is invalid. "
                         "Supported schemas include: %s" % (
                             document.get('schema', 'N/A'),
                             supported_schema_list))
            LOG.error(error_msg)
            result['errors'].append({
                'schema': document.get('schema', 'N/A'),
                'name': document.get('metadata', {}).get('name', 'N/A'),
                'message': error_msg,
                'path': '.'
            })

        for validator in self._validators:
            if validator.matches(document):
                error_outputs = validator.validate(document)
                if error_outputs:
                    for error_output in error_outputs:
                        result['errors'].append(error_output)

        if result['errors']:
            result.setdefault('status', 'failure')
        else:
            result.setdefault('status', 'success')

        return result

    def validate_all(self):
        """Pre-validate that all documents are correctly formatted.

        All concrete documents in the revision must successfully pass their
        JSON schema validations. The result of the validation is stored under
        the "deckhand-document-schema-validation" validation namespace for
        a document revision.

        All abstract documents must themselves be sanity-checked.

        Validation is broken up into 3 stages:

            1) Validate that each document contains the basic bulding blocks
               needed: i.e. ``schema`` and ``metadata`` using a "base" schema.
               Failing this validation is deemed a critical failure, resulting
               in an exception.

               .. note::

                   The ``data`` section, while mandatory, will not result in
                   critical failure. This is because a document can rely
                   on yet another document for ``data`` substitution. But
                   the validation for the document will be tagged as
                   ``failure``.

            2) Validate each specific document type (e.g. validation policy)
               using a more detailed schema. Failing this validation is deemed
               non-critical, resulting in the error being recorded along with
               any other non-critical exceptions, which are returned together
               later.

            3) Execute ``DataSchema`` validations if applicable.

        :returns: A list of validations (one for each document validated).
        :rtype: List[dict]
        :raises errors.InvalidDocumentFormat: If the document failed schema
            validation and the failure is deemed critical.
        :raises RuntimeError: If a Deckhand schema itself is invalid.

        """

        validation_results = []

        for document in self.documents:
            # NOTE(fmontei): Since ``DataSchema`` documents created in previous
            # revisions are retrieved and combined with new ``DataSchema``
            # documents, we only want to create a validation result in the DB
            # for the new documents. One way to do this is to check whether the
            # document contains the 'id' key which is only assigned by the DB.
            requires_validation = 'id' not in document

            if requires_validation:
                result = self._validate_one(document)
                validation_results.append(result)

        validations = self._format_validation_results(validation_results)
        return validations


def _get_schema_parts(document, schema_key='schema'):
    schema_parts = utils.jsonpath_parse(document, schema_key).split('/')
    schema_prefix = '/'.join(schema_parts[:2])
    schema_version = schema_parts[2]
    if schema_version.endswith('.0'):
        schema_version = schema_version[:-2]
    return schema_prefix, schema_version


def _generate_validation_error_output(schema, document, error, root_path):
    """Returns a formatted output with necessary details for debugging why
    a validation failed.

    The response is a dictionary with the following keys:

    * validation_schema: The schema body that was used to validate the
        document.
    * schema_path: The JSON path in the schema where the failure originated.
    * name: The document name.
    * schema: The document schema.
    * path: The JSON path in the document where the failure originated.
    * error_section: The "section" in the document above which the error
        originated (i.e. the dict in which ``path`` is found).
    * message: The error message returned by the ``jsonschema`` validator.

    :returns: Dictionary in the above format.
    """
    path_to_error_in_document = root_path + '.'.join(
        [str(x) for x in error.path])
    path_to_error_in_schema = '.' + '.'.join(
        [str(x) for x in error.schema_path])

    parent_path_to_error_in_document = '.'.join(
        path_to_error_in_document.split('.')[:-1]) or '.'
    try:
        parent_error_section = utils.jsonpath_parse(
            document, parent_path_to_error_in_document)
        if 'data' in parent_error_section:
            # NOTE(fmontei): Because validation is performed on fully rendered
            # documents, it is necessary to omit the parts of the data section
            # where substitution may have occurred to avoid exposing any
            # secrets. While this may make debugging a few validation failures
            # more difficult, it is a necessary evil.
            SecretsSubstitution.sanitize_potential_secrets(document)
    except Exception:
        parent_error_section = (
            'Failed to find parent section above where error occurred.')

    error_output = {
        'validation_schema': schema.schema,
        'schema_path': path_to_error_in_schema,
        'name': document.name,
        'schema': document.schema,
        'path': path_to_error_in_document,
        'error_section': parent_error_section,
        'message': error.message
    }

    return error_output
