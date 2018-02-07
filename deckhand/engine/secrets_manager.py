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

from oslo_log import log as logging
import six

from deckhand.barbican import driver
from deckhand.engine import document_wrapper
from deckhand import errors
from deckhand import utils

LOG = logging.getLogger(__name__)

CLEARTEXT = 'cleartext'
ENCRYPTED = 'encrypted'


class SecretsManager(object):
    """Internal API resource for interacting with Barbican.

    Currently only supports Barbican.
    """

    barbican_driver = driver.BarbicanDriver()

    def create(self, secret_doc):
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
        encryption_type = secret_doc['metadata']['storagePolicy']
        secret_type = self._get_secret_type(secret_doc['schema'])

        if encryption_type == ENCRYPTED:
            # Store secret_ref in database for `secret_doc`.
            kwargs = {
                'name': secret_doc['metadata']['name'],
                'secret_type': secret_type,
                'payload': secret_doc['data']
            }
            resp = self.barbican_driver.create_secret(**kwargs)

            secret_ref = resp['secret_ref']
            created_secret = secret_ref
        elif encryption_type == CLEARTEXT:
            created_secret = secret_doc['data']

        return created_secret

    def _get_secret_type(self, schema):
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

    def __init__(self, substitution_sources=None):
        """SecretSubstitution constructor.

        This class will automatically detect documents that require
        substitution; documents need not be filtered prior to being passed to
        the constructor.

        :param substitution_sources: List of documents that are potential
            sources for substitution. Should only include concrete documents.
        :type substitution_sources: List[dict]
        """

        self._substitution_sources = {}

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
                  ', '.join(['[%s] %s' % (d.schema, d.name)
                            for d in documents_to_substitute]))

        for document in documents_to_substitute:
            LOG.debug('Checking for substitutions for document [%s] %s.',
                      document.schema, document.name)
            for sub in document.substitutions:
                src_schema = sub['src']['schema']
                src_name = sub['src']['name']
                src_path = sub['src']['path']

                if not src_schema:
                    LOG.warning('Source document schema "%s" is unspecified '
                                'under substitutions for document [%s] %s.',
                                src_schema, document.schema, document.name)
                if not src_name:
                    LOG.warning('Source document name "%s" is unspecified'
                                ' under substitutions for document [%s] %s.',
                                src_name, document.schema, document.name)
                if not src_path:
                    LOG.warning('Source document path "%s" is unspecified '
                                'under substitutions for document [%s] %s.',
                                src_path, document.schema, document.name)

                if (src_schema, src_name) in self._substitution_sources:
                    src_doc = self._substitution_sources[
                        (src_schema, src_name)]
                else:
                    src_doc = {}
                    LOG.warning('Could not find substitution source document '
                                '[%s] %s among the provided '
                                '`substitution_sources`.', src_schema,
                                                           src_name)

                # If the data is a dictionary, retrieve the nested secret
                # via jsonpath_parse, else the secret is the primitive/string
                # stored in the data section itself.
                if isinstance(src_doc.get('data'), dict):
                    src_secret = utils.jsonpath_parse(src_doc.get('data', {}),
                                                      src_path)
                else:
                    src_secret = src_doc.get('data')

                dest_path = sub['dest']['path']
                dest_pattern = sub['dest'].get('pattern', None)

                if not dest_path:
                    LOG.warning('Destination document path "%s" is unspecified'
                                ' under substitutions for document [%s] %s.',
                                dest_path, document.schema, document.name)

                LOG.debug('Substituting from schema=%s name=%s src_path=%s '
                          'into dest_path=%s, dest_pattern=%s', src_schema,
                          src_name, src_path, dest_path, dest_pattern)
                try:
                    substituted_data = utils.jsonpath_replace(
                        document['data'], src_secret, dest_path, dest_pattern)
                    if isinstance(substituted_data, dict):
                        document['data'].update(substituted_data)
                    elif substituted_data:
                        document['data'] = substituted_data
                    else:
                        LOG.warning(
                            'Failed to create JSON path "%s" in the '
                            'destination document [%s] %s. No data was '
                            'substituted.', dest_path, document.schema,
                            document.name)
                except Exception as e:
                    LOG.error('Unexpected exception occurred while attempting '
                              'secret substitution. %s', six.text_type(e))
                    raise errors.SubstitutionFailure(details=six.text_type(e))

        yield document

    @staticmethod
    def sanitize_potential_secrets(document):
        """Sanitize all secret data that may have been substituted into the
        document. Uses references in ``document.substitutions`` to determine
        which values to sanitize. Only meaningful to call this on post-rendered
        documents.

        :param DocumentDict document: Document to sanitize.
        """
        to_sanitize = copy.deepcopy(document)
        safe_message = 'Sanitized to avoid exposing secret.'

        for sub in document.substitutions:
            replaced_data = utils.jsonpath_replace(
                to_sanitize['data'], safe_message, sub['dest']['path'])
            if replaced_data:
                to_sanitize['data'] = replaced_data

        return to_sanitize
