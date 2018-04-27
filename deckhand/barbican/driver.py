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

import ast
import re

import barbicanclient
from oslo_log import log as logging
from oslo_serialization import base64
from oslo_utils import uuidutils
import six

from deckhand.barbican import client_wrapper
from deckhand import errors
from deckhand import types

LOG = logging.getLogger(__name__)


class BarbicanDriver(object):

    _url_re = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|'
                         '(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    def __init__(self):
        self.barbicanclient = client_wrapper.BarbicanClientWrapper()

    @classmethod
    def is_barbican_ref(cls, secret_ref):
        # TODO(felipemonteiro): Query Keystone service catalog for Barbican
        # endpoint and cache it if Keystone is enabled. For now, it should be
        # enough to check that ``secret_ref`` is a valid URL, contains
        # 'secrets' substring, ends in a UUID and that the source document from
        # which the reference is extracted is encrypted.
        try:
            secret_uuid = secret_ref.split('/')[-1]
        except Exception:
            secret_uuid = None
        return (
            isinstance(secret_ref, six.string_types) and
            cls._url_re.match(secret_ref) and
            'secrets' in secret_ref and
            uuidutils.is_uuid_like(secret_uuid)
        )

    @staticmethod
    def _get_secret_type(schema):
        """Get the Barbican secret type based on the following mapping:

        ``deckhand/Certificate/v1`` => certificate
        ``deckhand/CertificateKey/v1`` => private
        ``deckhand/CertificateAuthority/v1`` => certificate
        ``deckhand/CertificateAuthorityKey/v1`` => private
        ``deckhand/Passphrase/v1`` => passphrase
        ``deckhand/PrivateKey/v1`` => private
        ``deckhand/PublicKey/v1`` => public
        Other => passphrase

        :param schema: The document's schema.
        :returns: The value corresponding to the mapping above.
        """
        parts = schema.split('/')
        if len(parts) == 3:
            namespace, kind, _ = parts
        elif len(parts) == 2:
            namespace, kind = parts
        else:
            raise ValueError(
                'Schema %s must consist of namespace/kind/version.' % schema)

        is_generic = (
            '/'.join([namespace, kind]) not in types.DOCUMENT_SECRET_TYPES
        )

        # If the document kind is not a built-in secret type, then default to
        # 'passphrase'.
        if is_generic:
            LOG.debug('Defaulting to secret_type="passphrase" for generic '
                      'document schema %s.', schema)
            return 'passphrase'

        kind = kind.lower()

        if kind in [
            'certificateauthoritykey', 'certificatekey', 'privatekey'
        ]:
            return 'private'
        elif kind == 'certificateauthority':
            return 'certificate'
        elif kind == 'publickey':
            return 'public'
        # NOTE(felipemonteiro): This branch below handles certificate and
        # passphrase, both of which are supported secret types in Barbican.
        return kind

    def _base64_encode_payload(self, secret_doc):
        """Ensures secret document payload is compatible with Barbican."""

        payload = secret_doc.data
        secret_type = self._get_secret_type(secret_doc.schema)

        # NOTE(felipemonteiro): The logic for the 2 conditions below is
        # enforced from Barbican's Python client. Some pre-processing and
        # transformation is needed to make Barbican work with non-compatible
        # formats.
        if not payload and payload is not False:
            # There is no point in even bothering to encrypt an empty
            # body, which just leads to needless overhead, so return
            # early.
            LOG.info('Barbican does not accept empty payloads so '
                     'Deckhand will not encrypt document [%s, %s] %s.',
                     secret_doc.schema, secret_doc.layer, secret_doc.name)
            secret_doc.storage_policy = types.CLEARTEXT
        elif not isinstance(
                payload, (six.text_type, six.binary_type)):
            LOG.debug('Forcibly setting secret_type=opaque and '
                      'base64-encoding non-string payload for '
                      'document [%s, %s] %s.', secret_doc.schema,
                      secret_doc.layer, secret_doc.name)
            # NOTE(felipemonteiro): base64-encoding the non-string payload is
            # done for serialization purposes, not for security purposes.
            # 'opaque' is used to avoid Barbican doing any further
            # serialization server-side.
            secret_type = 'opaque'
            try:
                payload = base64.encode_as_text(six.text_type(payload))
            except Exception:
                message = ('Failed to base64-encode payload of type %s '
                           'for Barbican storage.', type(payload))
                LOG.error(message)
                raise errors.UnknownSubstitutionError(
                    src_schema=secret_doc.schema,
                    src_layer=secret_doc.layer, src_name=secret_doc.name,
                    schema='N/A', layer='N/A', name='N/A', details=message)
        return secret_type, payload

    def create_secret(self, secret_doc):
        """Create a secret.

        :param secret_doc: Document with ``storagePolicy`` of "encrypted".
        :type secret_doc: document.DocumentDict
        :returns: Secret reference returned by Barbican
        :rtype: str
        """
        secret_type, payload = self._base64_encode_payload(secret_doc)

        if secret_doc.storage_policy == types.CLEARTEXT:
            return payload

        # Store secret_ref in database for `secret_doc`.
        kwargs = {
            'name': secret_doc['metadata']['name'],
            'secret_type': secret_type,
            'payload': payload
        }
        LOG.info('Storing encrypted document data in Barbican.')

        try:
            secret = self.barbicanclient.call("secrets.create", **kwargs)
            secret_ref = secret.store()
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPClientError,
                barbicanclient.exceptions.HTTPServerError) as e:
            LOG.error('Caught %s error from Barbican, likely due to a '
                      'configuration or deployment issue.',
                      e.__class__.__name__)
            raise errors.BarbicanException(details=str(e))
        except barbicanclient.exceptions.PayloadException as e:
            LOG.error('Caught %s error from Barbican, because the secret '
                      'payload type is unsupported.', e.__class__.__name__)
            raise errors.BarbicanException(details=str(e))

        return secret_ref

    def _base64_decode_payload(self, src_doc, dest_doc, payload):
        try:
            # If the secret_type is 'opaque' then this implies the
            # payload was encoded to base64 previously. Reverse the
            # operation.
            payload = ast.literal_eval(base64.decode_as_text(payload))
        except Exception:
            message = ('Failed to unencode the original payload that '
                       'presumably was encoded to base64 with '
                       'secret_type=opaque for document [%s, %s] %s.' %
                       src_doc.meta)
            LOG.error(message)
            raise errors.UnknownSubstitutionError(
                src_schema=src_doc.schema, src_layer=src_doc.layer,
                src_name=src_doc.name, schema=dest_doc.schema,
                layer=dest_doc.layer, name=dest_doc.name,
                details=message)
        return payload

    def get_secret(self, src_doc, dest_doc, secret_ref):
        """Get a secret."""
        try:
            secret = self.barbicanclient.call("secrets.get", secret_ref)
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPClientError,
                barbicanclient.exceptions.HTTPServerError,
                ValueError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanException(details=str(e))

        payload = secret.payload
        if secret.secret_type == 'opaque':
            LOG.debug('Forcibly base64-decoding original non-string payload '
                      'for document [%s, %s] %s.', *src_doc.meta)
            secret = self._base64_decode_payload(src_doc, dest_doc, payload)
        else:
            secret = payload

        return secret
