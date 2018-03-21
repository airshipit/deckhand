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
from oslo_utils import uuidutils
import six

from deckhand.barbican import driver
from deckhand.common import document as document_wrapper
from deckhand.common import utils
from deckhand import errors

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

CLEARTEXT = 'cleartext'
ENCRYPTED = 'encrypted'


class SecretsManager(object):
    """Internal API resource for interacting with Barbican.

    Currently only supports Barbican.
    """

    barbican_driver = driver.BarbicanDriver()

    _url_re = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|'
                         '(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    @classmethod
    def create(cls, secret_doc):
        """Securely store secrets contained in ``secret_doc``.

        Ordinarily, Deckhand documents are stored directly in Deckhand's
        database. However, secret data (contained in the data section for the
        documents with the schemas enumerated below) must be stored using a
        secure storage service like Barbican.

        Documents with ``metadata.storagePolicy`` == "clearText" have their
        secrets stored directly in Deckhand.

        Documents with ``metadata.storagePolicy`` == "encrypted" are stored in
        Barbican directly. Deckhand in turn stores the reference returned
        by Barbican in Deckhand.

        :param secret_doc: A Deckhand document with one of the following
            schemas:

                * ``deckhand/Certificate/v1``
                * ``deckhand/CertificateKey/v1``
                * ``deckhand/Passphrase/v1``

        :returns: Dictionary representation of
            ``deckhand.db.sqlalchemy.models.DocumentSecret``.
        """
        # TODO(fmontei): Look into POSTing Deckhand metadata into Barbican's
        # Secrets Metadata API to make it easier to track stale secrets from
        # prior revisions that need to be deleted.

        encryption_type = secret_doc['metadata']['storagePolicy']
        secret_type = cls._get_secret_type(secret_doc['schema'])

        if encryption_type == ENCRYPTED:
            # Store secret_ref in database for `secret_doc`.
            kwargs = {
                'name': secret_doc['metadata']['name'],
                'secret_type': secret_type,
                'payload': secret_doc['data']
            }
            resp = cls.barbican_driver.create_secret(**kwargs)

            secret_ref = resp['secret_ref']
            created_secret = secret_ref
        elif encryption_type == CLEARTEXT:
            created_secret = secret_doc['data']

        return created_secret

    @classmethod
    def _is_barbican_ref(cls, secret_ref):
        return (
            isinstance(secret_ref, six.string_types) and
                cls._url_re.match(secret_ref) and 'secrets' in secret_ref
        )

    @classmethod
    def get(cls, secret_ref):
        """Return a secret payload from Barbican if ``secret_ref`` is a
        Barbican secret reference or else return ``secret_ref``.

        Extracts {secret_uuid} from a secret reference and queries Barbican's
        Secrets API with it.

        :param str secret_ref:

            * String formatted like:
              "https://{barbican_host}/v1/secrets/{secret_uuid}"
              which results in a Barbican query.
            * Any other string which results in a pass-through.

        :returns: Secret payload from Barbican or ``secret_ref``.
        """

        # TODO(fmontei): Query Keystone service catalog for Barbican endpoint
        # and cache it if Keystone is enabled. For now, it should be enough
        # to check that ``secret_ref`` is a valid URL, contains 'secrets'
        # substring, ends in a UUID and that the source document from which
        # the reference is extracted is encrypted.
        if cls._is_barbican_ref(secret_ref):
            LOG.debug('Resolving Barbican secret using source document '
                      'reference...')
            try:
                secret_uuid = secret_ref.split('/')[-1]
            except Exception:
                secret_uuid = None
            if not uuidutils.is_uuid_like(secret_uuid):
                return secret_ref
        else:
            return secret_ref

        # TODO(fmontei): Need to avoid this call if Keystone is disabled.
        secret = cls.barbican_driver.get_secret(secret_ref=secret_uuid)
        payload = secret.payload
        LOG.debug('Successfully retrieved Barbican secret using reference.')
        return payload

    @classmethod
    def _get_secret_type(cls, schema):
        """Get the Barbican secret type based on the following mapping:

        ``deckhand/Certificate/v1`` => certificate
        ``deckhand/CertificateKey/v1`` => private
        ``deckhand/Passphrase/v1`` => passphrase

        :param schema: The document's schema.
        :returns: The value corresponding to the mapping above.
        """
        _schema = schema.split('/')[1].lower().strip()
        if _schema == 'certificatekey':
            return 'private'
        elif _schema == 'certificateauthority':
            return 'certificate'
        elif _schema == 'certificateauthoritykey':
            return 'private'
        elif _schema == 'publickey':
            return 'public'
        return _schema


class SecretsSubstitution(object):
    """Class for document substitution logic for YAML files."""

    __slots__ = ('_fail_on_missing_sub_src', '_substitution_sources')

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

    def __init__(self, substitution_sources=None,
                 fail_on_missing_sub_src=True):
        """SecretSubstitution constructor.

        This class will automatically detect documents that require
        substitution; documents need not be filtered prior to being passed to
        the constructor.

        :param substitution_sources: List of documents that are potential
            sources for substitution. Should only include concrete documents.
        :type substitution_sources: List[dict]
        :param bool fail_on_missing_sub_src: Whether to fail on a missing
            substitution source. Default is True.
        """

        # This maps a 2-tuple of (schema, name) to a document from which the
        # document.meta can be extracted which is a 3-tuple of (schema, layer,
        # name). This is necessary since the substitution format in the
        # document itself only provides a 2-tuple of (schema, name).
        self._substitution_sources = {}
        self._fail_on_missing_sub_src = fail_on_missing_sub_src

        for document in substitution_sources:
            if not isinstance(document, document_wrapper.DocumentDict):
                document = document_wrapper.DocumentDict(document)
            if document.schema and document.name:
                self._substitution_sources.setdefault(
                    (document.schema, document.name), document)

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
                               'sources.', src_schema, src_name)
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

                # If the document has storagePolicy == encrypted then resolve
                # the Barbican reference into the actual secret.
                if src_doc.is_encrypted:
                    try:
                        src_secret = SecretsManager.get(src_secret)
                    except errors.BarbicanException as e:
                        LOG.error(
                            'Failed to resolve a Barbican reference for '
                            'substitution source document [%s, %s] %s '
                            'referenced in document [%s, %s] %s. Details: %s',
                            src_schema, src_doc.layer, src_name,
                            document.schema, document.layer, document.name,
                            e.format_message())
                        raise errors.UnknownSubstitutionError(
                            src_schema=src_schema, src_layer=src_doc.layer,
                            src_name=src_name, schema=document.schema,
                            layer=document.layer, name=document.name,
                            details=e.format_message())

                dest_path = sub['dest']['path']
                dest_pattern = sub['dest'].get('pattern', None)

                LOG.debug('Substituting from schema=%s name=%s src_path=%s '
                          'into dest_path=%s, dest_pattern=%s', src_schema,
                          src_name, src_path, dest_path, dest_pattern)
                try:
                    exc_message = ''
                    substituted_data = utils.jsonpath_replace(
                        document['data'], src_secret, dest_path, dest_pattern)
                    if (isinstance(document['data'], dict)
                            and isinstance(substituted_data, dict)):
                        document['data'].update(substituted_data)
                    elif substituted_data:
                        document['data'] = substituted_data
                    else:
                        exc_message = (
                            'Failed to create JSON path "%s" in the '
                            'destination document [%s, %s] %s. No data was '
                            'substituted.', dest_path, document.schema,
                            document.layer, document.name)
                except Exception as e:
                    LOG.error('Unexpected exception occurred while attempting '
                              'substitution using source document [%s, %s] %s '
                              'referenced in [%s, %s] %s. Details: %s',
                              src_schema, src_name, src_doc.layer,
                              document.schema, document.layer, document.name,
                              six.text_type(e))
                    exc_message = six.text_type(e)
                finally:
                    if exc_message:
                        LOG.error(exc_message)
                        raise errors.UnknownSubstitutionError(
                            src_schema=src_schema, src_layer=src_doc.layer,
                            src_name=src_name, schema=document.schema,
                            layer=document.layer, name=document.name,
                            details=exc_message)

        yield document

    def update_substitution_sources(self, schema, name, data):
        if (schema, name) not in self._substitution_sources:
            return

        substitution_src = self._substitution_sources[(schema, name)]
        if isinstance(data, dict) and isinstance(substitution_src.data, dict):
            substitution_src.data.update(data)
        else:
            substitution_src.data = data
