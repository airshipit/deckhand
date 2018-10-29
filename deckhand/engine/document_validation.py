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
import copy
import os
import pkg_resources
import re
import yaml

import jsonschema
from oslo_log import log as logging
import six

from deckhand.common import document as document_wrapper
from deckhand.common import utils
from deckhand.common import validation_message as vm
from deckhand.engine.secrets_manager import SecretsSubstitution
from deckhand import errors
from deckhand import types

LOG = logging.getLogger(__name__)

_DEFAULT_SCHEMAS = {}
_SUPPORTED_SCHEMA_VERSIONS = ('v1',)


def _get_schema_parts(document, schema_key='schema'):
    schema_parts = utils.jsonpath_parse(document, schema_key).split('/')
    schema_prefix = '/'.join(schema_parts[:2])
    schema_version = schema_parts[2]
    return schema_prefix, schema_version


def _get_schema_dir():
    return pkg_resources.resource_filename('deckhand.engine', 'schemas')


def _build_schema_map():
    """Populates ``_DEFAULT_SCHEMAS`` with built-in Deckhand schemas."""
    global _DEFAULT_SCHEMAS
    _DEFAULT_SCHEMAS = {k: {} for k in _SUPPORTED_SCHEMA_VERSIONS}
    schema_dir = _get_schema_dir()
    for schema_file in os.listdir(schema_dir):
        if not schema_file.endswith('.yaml'):
            continue
        with open(os.path.join(schema_dir, schema_file)) as f:
            for schema in yaml.safe_load_all(f):
                schema_name = schema['metadata']['name']
                version = schema_name.split('/')[-1]
                _DEFAULT_SCHEMAS.setdefault(version, {})
                if schema_file in _DEFAULT_SCHEMAS[version]:
                    raise RuntimeError("Duplicate DataSchema document [%s] %s "
                                       "detected." % (schema['schema'],
                                                      schema_name))
                _DEFAULT_SCHEMAS[version].setdefault(
                    '/'.join(schema_name.split('/')[:2]), schema['data'])


_build_schema_map()


@six.add_metaclass(abc.ABCMeta)
class BaseValidator(object):
    """Abstract base validator.

    Sub-classes should override this to implement schema-specific document
    validation.
    """

    __slots__ = ('_schema_map')

    _supported_versions = ('v1',)
    _schema_re = re.compile(r'^[a-zA-Z]+\/[a-zA-Z]+\/v\d+$')

    def __init__(self):
        global _DEFAULT_SCHEMAS
        self._schema_map = _DEFAULT_SCHEMAS

    @abc.abstractmethod
    def validate(self, document):
        """Validate whether ``document`` passes schema validation."""


class GenericValidator(BaseValidator):
    """Validator used for validating all documents, regardless whether concrete
    or abstract, or what version its schema is.
    """

    __slots__ = ('base_schema')

    _diagnostic = (
        'Ensure that each document has a metadata, schema and data section. '
        'Each document must pass the schema defined under: '
        'https://airship-deckhand.readthedocs.io/en/latest/'
        'validation.html#base-schema')

    def __init__(self):
        super(GenericValidator, self).__init__()
        self.base_schema = self._schema_map['v1']['deckhand/Base']

    def validate_metadata(self, metadata):
        """Validate ``metadata`` against the given schema.

        The ``metadata`` section of a Deckhand document describes a schema
        defining just the ``metadata`` section. Use that declaration to
        choose a schema for validating ``metadata``.

        :param dict metadata: Document metadata section to validate
        :returns: list of validation errors or empty list for success
        """
        errors = list()

        schema_name, schema_ver = _get_schema_parts(metadata)
        schema = self._schema_map.get(schema_ver, {}).get(schema_name, {})

        if not schema:
            return ['Invalid metadata schema %s version %s specified.'
                    % (schema_name, schema_ver)]

        LOG.debug("Validating document metadata with schema %s/%s.",
                  schema_name, schema_ver)
        jsonschema.Draft4Validator.check_schema(schema)
        schema_validator = jsonschema.Draft4Validator(schema)
        errors.extend([e.message
                       for e in schema_validator.iter_errors(metadata)])
        return errors

    def validate(self, document, **kwargs):
        """Validate ``document`` against basic schema validation.

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
            jsonschema.Draft4Validator.check_schema(self.base_schema)
            schema_validator = jsonschema.Draft4Validator(self.base_schema)
            error_messages = [
                e.message for e in schema_validator.iter_errors(document)]

            if not error_messages:
                error_messages.extend(
                    self.validate_metadata(document.metadata))
        except Exception as e:
            raise RuntimeError(
                'Unknown error occurred while attempting to use Deckhand '
                'schema. Details: %s' % six.text_type(e))
        else:
            if error_messages:
                LOG.error(
                    'Failed sanity-check validation for document [%s, %s] %s. '
                    'Details: %s', document.schema, document.layer,
                    document.name, error_messages)
                raise errors.InvalidDocumentFormat(
                    error_list=[
                        vm.ValidationMessage(
                            message=message,
                            name=vm.DOCUMENT_SANITY_CHECK_FAILURE,
                            doc_schema=document.schema,
                            doc_name=document.name,
                            doc_layer=document.layer,
                            diagnostic=self._diagnostic)
                        for message in error_messages
                    ],
                    reason='Validation'
                )


class DataSchemaValidator(GenericValidator):
    """Validator for validating ``DataSchema`` documents."""

    __slots__ = ('_default_schema_map', '_current_data_schemas')

    def _build_schema_map(self, data_schemas):
        schema_map = copy.deepcopy(self._default_schema_map)

        for data_schema in data_schemas:
            # Ensure that each `DataSchema` document has required properties
            # before they themselves can be used to validate other documents.
            if not data_schema.name:
                continue
            if self._schema_re.match(data_schema.name) is None:
                continue
            if not data_schema.data:
                continue
            schema_prefix, schema_version = _get_schema_parts(
                data_schema, 'metadata.name')
            schema_map[schema_version].setdefault(schema_prefix,
                                                  data_schema.data)

        return schema_map

    def __init__(self, data_schemas):
        super(DataSchemaValidator, self).__init__()
        global _DEFAULT_SCHEMAS

        self._default_schema_map = _DEFAULT_SCHEMAS
        self._current_data_schemas = [d.data for d in data_schemas]
        self._schema_map = self._build_schema_map(data_schemas)

    def _generate_validation_error_output(self, schema, document, error,
                                          root_path):
        """Returns a formatted output with necessary details for debugging why
        a validation failed.

        The response is a dictionary with the following keys:

        * validation_schema: The schema body that was used to validate the
            document.
        * schema_path: The JSON path in the schema where the failure
                       originated.
        * name: The document name.
        * schema: The document schema.
        * path: The JSON path in the document where the failure originated.
        * error_section: The "section" in the document above which the error
            originated (i.e. the dict in which ``path`` is found).
        * message: The error message returned by the ``jsonschema`` validator.

        :returns: Dictionary in the above format.
        """
        error_path = '.'.join([str(x) for x in error.path])
        if error_path:
            path_to_error_in_document = '.'.join([root_path, error_path])
        else:
            path_to_error_in_document = root_path
        path_to_error_in_schema = '.' + '.'.join(
            [str(x) for x in error.schema_path])

        parent_path_to_error_in_document = '.'.join(
            path_to_error_in_document.split('.')[:-1]) or '.'
        try:
            # NOTE(felipemonteiro): Because validation is performed on fully
            # rendered documents, it is necessary to omit the parts of the data
            # section where substitution may have occurred to avoid exposing
            # any secrets. While this may make debugging a few validation
            # failures more difficult, it is a necessary evil.
            sanitized_document = (
                SecretsSubstitution.sanitize_potential_secrets(
                    error, document))
            # This incurs some degree of overhead as caching here won't make
            # a big difference as we are not parsing commonly referenced
            # JSON paths -- but this branch is only hit during error handling
            # so this should be OK.
            parent_error_section = utils.jsonpath_parse(
                sanitized_document, parent_path_to_error_in_document)
        except Exception:
            parent_error_section = (
                'Failed to find parent section above where error occurred.')

        error_output = {
            'validation_schema': schema,
            'schema_path': path_to_error_in_schema,
            'name': document.name,
            'schema': document.schema,
            'layer': document.layer,
            'path': path_to_error_in_document,
            'error_section': parent_error_section,
            'message': error.message
        }

        return error_output

    def _get_schemas(self, document):
        """Retrieve the relevant schemas based on the document's ``schema``.

        :param dict doc: The document used for finding the correct schema
            to validate it based on its ``schema``.
        :returns: A schema to be used by ``jsonschema`` for document
            validation.
        :rtype: dict

        """
        schema_prefix, schema_version = _get_schema_parts(document)
        matching_schemas = []

        relevant_schemas = self._schema_map.get(schema_version, {})
        for candidate_schema_prefix, schema in relevant_schemas.items():
            if candidate_schema_prefix == schema_prefix:
                if schema not in matching_schemas:
                    matching_schemas.append(schema)
        return matching_schemas

    def validate(self, document, pre_validate=True):
        """Validate ``document`` against built-in ``schema``-specific schemas.

        Does not apply to abstract documents.

        :param document: Document to validate.
        :type document: DocumentDict
        :param pre_validate: Whether to pre-validate documents using built-in
            schema validation. Skips over externally registered ``DataSchema``
            documents to avoid false positives. Default is True.
        :type pre_validate: bool
        :raises RuntimeError: If the Deckhand schema itself is invalid.
        :returns: Tuple of (error message, parent path for failing property)
            following schema validation failure.
        :rtype: Generator[Tuple[str, str]]

        """
        super(DataSchemaValidator, self).validate(document)

        # if this is a pre_validate, the only validation needed is structural
        # for non-control documents
        if not document.is_control and pre_validate:
            return

        if document.is_abstract:
            LOG.info('Skipping schema validation for abstract document [%s, '
                     '%s] %s.', *document.meta)
            return

        schemas_to_use = self._get_schemas(document)
        if not schemas_to_use:
            LOG.debug('Document schema %s not recognized by %s. No further '
                      'validation required.', document.schema,
                      self.__class__.__name__)

        for schema in schemas_to_use:
            root_path = '.data'

            try:
                jsonschema.Draft4Validator.check_schema(schema)
                schema_validator = jsonschema.Draft4Validator(schema)
                errors = schema_validator.iter_errors(document.get('data', {}))
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
                    yield self._generate_validation_error_output(
                        schema, document, error, root_path)


class DuplicateDocumentValidator(BaseValidator):
    """Validator used for guarding against duplicate documents."""

    def __init__(self):
        super(DuplicateDocumentValidator, self).__init__()
        self._document_history = set()
        self._diagnostic = ('Ensure that each raw document has a unique '
                            'combination of (name, schema, '
                            'metadata.layeringDefinition.layer).')

    def validate(self, document, **kwargs):
        """Validates that duplicate document doesn't exist."""
        if document.meta in self._document_history:
            validation_message = vm.ValidationMessage(
                message="Duplicate document exists",
                doc_schema=document.schema,
                doc_name=document.name,
                doc_layer=document.layer,
                diagnostic=self._diagnostic)
            return [validation_message.format_message()]
        else:
            self._document_history.add(document.meta)
        return []


class DocumentValidation(object):

    def __init__(self, documents, existing_data_schemas=None,
                 pre_validate=True):
        """Class for document validation logic for documents.

        This class is responsible for validating documents according to their
        schema.

        If ``pre_validate`` is true, then:

        * the base_schema validates ALL documents
        * ALL built-in schemas validate the appropriate
          document given a schema match
        * NO externally registered DataSchema documents
          are used for validation

        Else:

        * the base_schema validates ALL documents
        * ALL built-in schemas validate the appropriate
          document given a schema match
        * ALL externally registered DataSchema documents
          are used for validation given a schema match

        :param documents: Documents to be validated.
        :type documents: List[dict]
        :param existing_data_schemas: ``DataSchema`` documents created in prior
            revisions to be used to validate the "data" section of each
            document in ``documents``. Additional ``DataSchema`` documents in
            ``documents`` are combined with these.
        :type existing_data_schemas: dict or List[dict]
        :param pre_validate: Whether to pre-validate documents using built-in
            schema validation. Skips over externally registered ``DataSchema``
            documents to avoid false positives. Default is True.
        :type pre_validate: bool
        """

        self._documents = []
        self._current_data_schemas = [document_wrapper.DocumentDict(d)
                                      for d in existing_data_schemas or []]
        data_schema_map = {d.meta: d for d in self._current_data_schemas}

        raw_properties = ('data', 'metadata', 'schema')

        if not isinstance(documents, list):
            documents = [documents]
        for document in documents:
            # For post-validation documents are retrieved from the DB so those
            # DB properties need to be stripped to avoid validation errors.
            raw_document = {}
            for prop in raw_properties:
                raw_document[prop] = document.get(prop)

            document = document_wrapper.DocumentDict(raw_document)
            if document.schema.startswith(types.DATA_SCHEMA_SCHEMA):
                self._current_data_schemas.append(document)
                # If a newer version of the same DataSchema was passed in,
                # only use the new one and discard the old one.
                if document.meta in data_schema_map:
                    self._current_data_schemas.remove(
                        data_schema_map.pop(document.meta))

            self._documents.append(document)

        self._pre_validate = pre_validate

        self._validators = [
            DataSchemaValidator(self._current_data_schemas),
        ]
        if self._pre_validate:
            # Only perform this additional validation "offline". The controller
            # need not call this as the db module will handle this validation.
            self._validators.append(DuplicateDocumentValidator())

    def _get_supported_schema_list(self):
        schema_list = []
        validator = self._validators[-1]
        for schema_version, schema_map in validator._schema_map.items():
            for schema_name in schema_map:
                schema_list.append(schema_name + '/' + schema_version)
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
            message = ("The provided document schema %s is not registered. "
                       "Registered schemas include: %s" % (
                           document.get('schema', 'N/A'),
                           supported_schema_list))
            LOG.info(message)

        for validator in self._validators:
            error_outputs = validator.validate(
                document, pre_validate=self._pre_validate)
            if error_outputs:
                result['errors'].extend(error_outputs)

        if result['errors']:
            result.setdefault('status', 'failure')
        else:
            result.setdefault('status', 'success')

        return result

    def validate_all(self):
        """Validate that all documents are correctly formatted.

        All concrete documents in the revision must successfully pass their
        JSON schema validations. The result of the validation is stored under
        the "deckhand-document-schema-validation" validation namespace for
        a document revision.

        All abstract documents must themselves be sanity-checked.

        Validation is broken up into 2 "main" stages:

            1) Validate that each document contains the basic bulding blocks
               needed: i.e. ``schema`` and ``metadata`` using a "base" schema.
               Failing this validation is deemed a critical failure, resulting
               in an exception.

            2) Execute ``DataSchema`` validations if applicable. Includes all
               built-in ``DataSchema`` documents by default.

        :returns: A list of validations (one for each document validated).
        :rtype: List[dict]
        :raises errors.InvalidDocumentFormat: If the document failed schema
            validation and the failure is deemed critical.
        :raises RuntimeError: If a Deckhand schema itself is invalid.

        """

        validation_results = []

        for document in self._documents:
            result = self._validate_one(document)
            validation_results.append(result)

        return self._format_validation_results(validation_results)
