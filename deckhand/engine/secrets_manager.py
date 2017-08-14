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

from deckhand.barbican import driver

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

        Documents with metadata.storagePolicy == "clearText" have their secrets
        stored directly in Deckhand.

        Documents with metadata.storagePolicy == "encrypted" are stored in
        Barbican directly. Deckhand in turn stores the reference returned
        by Barbican in Deckhand.

        :param secret_doc: A Deckhand document with one of the following
            schemas:

                * deckhand/Certificate/v1
                * deckhand/CertificateKey/v1
                * deckhand/Passphrase/v1

        :returns: Dictionary representation of
            `deckhand.db.sqlalchemy.models.DocumentSecret`.
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

        deckhand/Certificate/v1 => certificate
        deckhand/CertificateKey/v1 => private
        deckhand/Passphrase/v1 => passphrase

        :param schema: The document's schema.
        :returns: The value corresponding to the mapping above.
        """
        _schema = schema.split('/')[1].lower().strip()
        if _schema == 'certificatekey':
            return 'private'
        return _schema
