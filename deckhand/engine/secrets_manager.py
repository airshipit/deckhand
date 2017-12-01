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

from oslo_log import log as logging

from deckhand.barbican import driver
from deckhand.db.sqlalchemy import api as db_api
from deckhand.engine import document as document_wrapper
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

            secret_ref = resp['secret_href']
            created_secret = {'secret': secret_ref}
        elif encryption_type == CLEARTEXT:
            created_secret = {'secret': secret_doc['data']}

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
        return _schema


class SecretsSubstitution(object):
    """Class for document substitution logic for YAML files."""

    def __init__(self, documents):
        """SecretSubstitution constructor.

        :param documents: List of documents that are candidates for secret
            substitution. This class will automatically detect documents that
            require substitution; documents need not be filtered prior to being
            passed to the constructor.
        """
        if not isinstance(documents, (list, tuple)):
            documents = [documents]

        self.docs_to_sub = []

        for document in documents:
            if not isinstance(document, document_wrapper.Document):
                document_obj = document_wrapper.Document(document)
                if document_obj.get_substitutions():
                    self.docs_to_sub.append(document_obj)

    def substitute_all(self):
        """Substitute all documents that have a `metadata.substitutions` field.

        Concrete (non-abstract) documents can be used as a source of
        substitution into other documents. This substitution is
        layer-independent, a document in the region layer could insert data
        from a document in the site layer.

        :returns: List of fully substituted documents.
        """
        LOG.debug('Substituting secrets for documents: %s',
                  self.docs_to_sub)
        substituted_docs = []

        for doc in self.docs_to_sub:
            LOG.debug(
                'Checking for substitutions in schema=%s, metadata.name=%s',
                doc.get_name(), doc.get_schema())
            for sub in doc.get_substitutions():
                src_schema = sub['src']['schema']
                src_name = sub['src']['name']
                src_path = sub['src']['path']
                if src_path == '.':
                    src_path = '.secret'

                # TODO(fmontei): Use SecretsManager for this logic. Need to
                # check Barbican for the secret if it has been encrypted.
                src_doc = db_api.document_get(
                    schema=src_schema, name=src_name, is_secret=True,
                    **{'metadata.layeringDefinition.abstract': False})
                src_secret = utils.jsonpath_parse(src_doc['data'], src_path)

                dest_path = sub['dest']['path']
                dest_pattern = sub['dest'].get('pattern', None)

                LOG.debug('Substituting from schema=%s name=%s src_path=%s '
                          'into dest_path=%s, dest_pattern=%s', src_schema,
                          src_name, src_path, dest_path, dest_pattern)
                substituted_data = utils.jsonpath_replace(
                    doc['data'], src_secret, dest_path, dest_pattern)
                doc['data'].update(substituted_data)

            substituted_docs.append(doc.to_dict())
        return substituted_docs
