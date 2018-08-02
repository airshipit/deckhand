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
import re

from oslo_config import cfg
from oslo_log import log as logging
import six

from deckhand.barbican.driver import BarbicanDriver
from deckhand.common import document as document_wrapper
from deckhand.common import utils
from deckhand import errors

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class SecretsManager(object):
    """Internal API resource for interacting with Barbican.

    Currently only supports Barbican.
    """

    barbican_driver = BarbicanDriver()

    @staticmethod
    def requires_encryption(document):
        clazz = document_wrapper.DocumentDict
        if not isinstance(document, clazz):
            document = clazz(document)
        return document.is_encrypted

    @classmethod
    def create(cls, secret_doc):
        """Securely store secrets contained in ``secret_doc``.

        Documents with ``metadata.storagePolicy`` == "clearText" have their
        secrets stored directly in Deckhand.

        Documents with ``metadata.storagePolicy`` == "encrypted" are stored in
        Barbican directly. Deckhand in turn stores the reference returned
        by Barbican in its own DB.

        :param secret_doc: A Deckhand document with a schema that belongs to
            ``types.DOCUMENT_SECRET_TYPES``.

        :returns: Unecrypted data section from ``secret_doc`` if the document's
            ``storagePolicy`` is "cleartext" or a Barbican secret reference
            if the ``storagePolicy`` is "encrypted'.
        """
        # TODO(fmontei): Look into POSTing Deckhand metadata into Barbican's
        # Secrets Metadata API to make it easier to track stale secrets from
        # prior revisions that need to be deleted.
        if not isinstance(secret_doc, document_wrapper.DocumentDict):
            secret_doc = document_wrapper.DocumentDict(secret_doc)

        if secret_doc.is_encrypted:
            payload = cls.barbican_driver.create_secret(secret_doc)
        else:
            payload = secret_doc.data
        return payload

    @classmethod
    def get(cls, secret_ref, src_doc):
        """Retrieve a secret payload from Barbican.

        Extracts {secret_uuid} from a secret reference and queries Barbican's
        Secrets API with it.

        :param str secret_ref: A string formatted like:
            "https://{barbican_host}/v1/secrets/{secret_uuid}"
        :returns: Secret payload from Barbican.
        """
        LOG.debug('Resolving Barbican secret using source document '
                  'reference...')
        secret = cls.barbican_driver.get_secret(secret_ref=secret_ref,
                                                src_doc=src_doc)
        LOG.debug('Successfully retrieved Barbican secret using reference.')
        return secret

    @classmethod
    def delete(cls, document):
        """Delete a secret from Barbican.

        :param dict document: Document with secret_ref in ``data`` section with
            format: "https://{barbican_host}/v1/secrets/{secret_uuid}"
        :returns: None

        """
        if not isinstance(document, document_wrapper.DocumentDict):
            document = document_wrapper.DocumentDict(document)

        secret_ref = document.data
        if document.is_encrypted and document.has_barbican_ref:
            LOG.debug('Deleting Barbican secret: %s.', secret_ref)
            cls.barbican_driver.delete_secret(secret_ref=secret_ref)
        else:
            LOG.warning('%s is not a valid Barbican secret. Could not delete.',
                        secret_ref)


class SecretsSubstitution(object):
    """Class for document substitution logic for YAML files."""

    __slots__ = ('_fail_on_missing_sub_src', '_substitution_sources',
                 '_encryption_sources')

    _insecure_reg_exps = (
        re.compile(r'^.* is not of type .+$'),
    )

    @staticmethod
    def sanitize_potential_secrets(error, document):
        """Sanitize all secret data that may have been substituted into the
        document or contained in the document itself (if the document has
        ``metadata.storagePolicy`` == 'encrypted'). Uses references in
        ``document.substitutions`` to determine which values to sanitize. Only
        meaningful to call this on post-rendered documents.

        :param error: Error message produced by ``jsonschema``.
        :param document: Document to sanitize.
        :type document: DocumentDict
        """
        if not document.substitutions and not document.is_encrypted:
            return document

        to_sanitize = copy.deepcopy(document)
        safe_message = 'Sanitized to avoid exposing secret.'

        # Sanitize any secrets contained in `error.message` referentially.
        if error.message and any(
                r.match(error.message)
                for r in SecretsSubstitution._insecure_reg_exps):
            error.message = safe_message

        # Sanitize any secrets extracted from the document itself.
        for sub in document.substitutions:
            replaced_data = utils.jsonpath_replace(
                to_sanitize['data'], safe_message, sub['dest']['path'])
            if replaced_data:
                to_sanitize['data'] = replaced_data

        return to_sanitize

    def get_unencrypted_data(self, secret_ref, src_doc, dest_doc):
        if secret_ref not in self._encryption_sources:
            LOG.error(
                'Secret reference %s not found among `encryption_sources`, '
                'referenced by source document [%s, %s] %s, needed by '
                'destination document [%s, %s] %s.', secret_ref,
                src_doc.schema, src_doc.layer, src_doc.name,
                dest_doc.schema, dest_doc.layer, dest_doc.name)
            raise errors.EncryptionSourceNotFound(
                secret_ref=secret_ref, schema=src_doc.schema,
                layer=src_doc.layer, name=src_doc.name)
        return self._encryption_sources[secret_ref]

    def __init__(self, substitution_sources=None,
                 fail_on_missing_sub_src=True, encryption_sources=None):
        """SecretSubstitution constructor.

        This class will automatically detect documents that require
        substitution; documents need not be filtered prior to being passed to
        the constructor.

        :param substitution_sources: List of documents that are potential
            sources for substitution. Or dict of documents keyed on tuple of
            (schema, metadata.name). Should only include concrete documents.
        :type substitution_sources: List[dict] or dict
        :param bool fail_on_missing_sub_src: Whether to fail on a missing
            substitution source. Default is True.
        :param encryption_sources: A dictionary that maps the reference
            contained in the destination document's data section to the
            actual unecrypted data. If encrypting data with Barbican, the
            reference will be a Barbican secret reference.
        :type encryption_sources: dict
        """

        # This maps a 2-tuple of (schema, name) to a document from which the
        # document.meta can be extracted which is a 3-tuple of (schema, layer,
        # name). This is necessary since the substitution format in the
        # document itself only provides a 2-tuple of (schema, name).
        self._substitution_sources = {}
        self._encryption_sources = encryption_sources or {}
        self._fail_on_missing_sub_src = fail_on_missing_sub_src

        if isinstance(substitution_sources, dict):
            self._substitution_sources = substitution_sources
        else:
            self._substitution_sources = dict()
            for document in substitution_sources:
                if not isinstance(document, document_wrapper.DocumentDict):
                    document = document_wrapper.DocumentDict(document)
                if document.schema and document.name:
                    self._substitution_sources.setdefault(
                        (document.schema, document.name), document)

    def _handle_unknown_substitution_exc(self, exc_message, src_doc, dest_doc):
        if self._fail_on_missing_sub_src:
            LOG.error(exc_message)
            raise errors.UnknownSubstitutionError(
                src_schema=src_doc.schema, src_layer=src_doc.layer,
                src_name=src_doc.name, schema=dest_doc.schema,
                layer=dest_doc.layer, name=dest_doc.name, details=exc_message)
        else:
            LOG.warning(exc_message)

    def _check_src_secret_is_not_none(self, src_secret, src_path, src_doc,
                                      dest_doc):
        if src_secret is None:
            if self._fail_on_missing_sub_src:
                raise errors.SubstitutionSourceDataNotFound(
                    src_path=src_path, src_schema=src_doc.schema,
                    src_layer=src_doc.layer, src_name=src_doc.name,
                    dest_schema=dest_doc.schema, dest_layer=dest_doc.layer,
                    dest_name=dest_doc.name)
            else:
                LOG.warning('Could not find source path %s in source document '
                            'or the secret extracted is None. Source document:'
                            ' [%s, %s] %s. Destination document: [%s, %s] %s.',
                            src_path, src_doc.schema, src_doc.layer,
                            src_doc.name, dest_doc.schema, dest_doc.layer,
                            dest_doc.name)

    def substitute_all(self, documents):
        """Substitute all documents that have a `metadata.substitutions` field.

        Concrete (non-abstract) documents can be used as a source of
        substitution into other documents. This substitution is
        layer-independent, a document in the region layer could insert data
        from a document in the site layer.

        :param documents: List of documents that are candidates for
            substitution.
        :type documents: dict or List[dict]
        :returns: List of fully substituted documents.
        :rtype: Generator[:class:`DocumentDict`]
        :raises SubstitutionSourceNotFound: If a substitution source document
            is referenced by another document but wasn't found.
        :raises UnknownSubstitutionError: If an unknown error occurred during
            substitution.
        """

        documents_to_substitute = []
        if not isinstance(documents, list):
            documents = [documents]

        for document in documents:
            if not isinstance(document, document_wrapper.DocumentDict):
                document = document_wrapper.DocumentDict(document)
            # If the document has substitutions include it.
            if document.substitutions:
                documents_to_substitute.append(document)

        LOG.debug('Performing substitution on following documents: %s',
                  ', '.join(['[%s, %s] %s' % d.meta
                             for d in documents_to_substitute]))

        for document in documents_to_substitute:
            LOG.debug('Checking for substitutions for document [%s, %s] %s.',
                      *document.meta)
            for sub in document.substitutions:
                src_schema = sub['src']['schema']
                src_name = sub['src']['name']
                src_path = sub['src']['path']

                if (src_schema, src_name) in self._substitution_sources:
                    src_doc = self._substitution_sources[
                        (src_schema, src_name)]
                else:
                    message = ('Could not find substitution source document '
                               '[%s] %s among the provided substitution '
                               'sources.' % (src_schema, src_name))
                    if self._fail_on_missing_sub_src:
                        LOG.error(message)
                        raise errors.SubstitutionSourceNotFound(
                            src_schema=src_schema, src_name=src_name,
                            document_schema=document.schema,
                            document_name=document.name)
                    else:
                        LOG.warning(message)
                        continue

                # If the data is a dictionary, retrieve the nested secret
                # via jsonpath_parse, else the secret is the primitive/string
                # stored in the data section itself.
                if isinstance(src_doc.get('data'), dict):
                    src_secret = utils.jsonpath_parse(src_doc.get('data', {}),
                                                      src_path)
                else:
                    src_secret = src_doc.get('data')

                self._check_src_secret_is_not_none(src_secret, src_path,
                                                   src_doc, document)

                # If the document has storagePolicy == encrypted then resolve
                # the Barbican reference into the actual secret.
                if src_doc.is_encrypted and src_doc.has_barbican_ref:
                    src_secret = self.get_unencrypted_data(src_secret, src_doc,
                                                           document)

                if not isinstance(sub['dest'], list):
                    dest_array = [sub['dest']]
                else:
                    dest_array = sub['dest']

                for each_dest_path in dest_array:
                    dest_path = each_dest_path['path']
                    dest_pattern = each_dest_path.get('pattern', None)

                    LOG.debug('Substituting from schema=%s layer=%s name=%s '
                              'src_path=%s into dest_path=%s, dest_pattern=%s',
                              src_schema, src_doc.layer, src_name, src_path,
                              dest_path, dest_pattern)

                    try:
                        exc_message = ''
                        substituted_data = utils.jsonpath_replace(
                            document['data'], src_secret,
                            dest_path, dest_pattern)
                        if (isinstance(document['data'], dict) and
                                isinstance(substituted_data, dict)):
                            document['data'].update(substituted_data)
                        elif substituted_data:
                            document['data'] = substituted_data
                        else:
                            exc_message = (
                                'Failed to create JSON path "%s" in the '
                                'destination document [%s, %s] %s. '
                                'No data was substituted.' % (
                                    dest_path, document.schema,
                                    document.layer, document.name))
                    except Exception as e:
                        LOG.error('Unexpected exception occurred '
                                  'while attempting '
                                  'substitution using '
                                  'source document [%s, %s] %s '
                                  'referenced in [%s, %s] %s. Details: %s',
                                  src_schema, src_name, src_doc.layer,
                                  document.schema, document.layer,
                                  document.name,
                                  six.text_type(e))
                        exc_message = six.text_type(e)
                    finally:
                        if exc_message:
                            self._handle_unknown_substitution_exc(
                                exc_message, src_doc, document)

        yield document

    def update_substitution_sources(self, meta, data):
        """Update substitution sources with rendered data so that future
        layering and substitution sources reference the latest rendered data
        rather than stale data.

        :param meta: Tuple of (schema, layer, name).
        :type meta: tuple
        :param data: Dictionary of just-rendered document data that belongs
            to the document uniquely identified by ``meta``.
        :type data: dict
        :returns None
        """
        schema, layer, name = meta

        if (schema, name) not in self._substitution_sources:
            return

        # Substitution sources only use schema/name which doesn't uniquely
        # identify replacement documents. The check below ensures that the
        # exact document is selected. Note that Deckhand prioritizes the
        # child-replacement to be rendered immediately after the
        # parent-replacement document, meaning that the child-replacement
        # document will be the one who correctly updates the substitution
        # sources below (which don't include parent-replacement documents).
        # Afterward, all other documents that reference the parent-replacement
        # should get the correct data.
        substitution_src = self._substitution_sources[(schema, name)]
        if substitution_src.meta != meta:
            return

        if isinstance(data, dict) and isinstance(substitution_src.data, dict):
            substitution_src.data.update(data)
        else:
            substitution_src.data = data
