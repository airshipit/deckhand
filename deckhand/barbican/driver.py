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
import time

import barbicanclient
from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import base64
from oslo_utils import excutils

from deckhand.barbican import cache
from deckhand.barbican import client_wrapper
from deckhand import errors
from deckhand import types

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class BarbicanDriver(object):

    def __init__(self):
        self.barbicanclient = client_wrapper.BarbicanClientWrapper()

    def _base64_encode_payload(self, secret_doc):
        """Ensures secret document payload is compatible with Barbican."""

        payload = secret_doc.data
        secret_type = None
        # Explicitly list the "empty" payloads we are refusing to store.
        # We don't use ``if not payload`` because that would not encrypt
        # and store something like ``data: !!int 0``
        if payload in ('', {}, [], None):
            # There is no point in even bothering to encrypt an empty
            # body, which just leads to needless overhead, so return
            # early.
            LOG.info('Barbican does not accept empty payloads so '
                     'Deckhand will not encrypt document [%s, %s] %s.',
                     secret_doc.schema, secret_doc.layer, secret_doc.name)
            secret_doc.storage_policy = types.CLEARTEXT
        else:
            LOG.debug('Setting secret_type=opaque and '
                      'base64-encoding payload of type %s for '
                      'document [%s, %s] %s.', type(payload),
                      secret_doc.schema, secret_doc.layer, secret_doc.name)
            secret_type = 'opaque'  # nosec  # not a hardcoded password
            try:
                payload = base64.encode_as_text(repr(payload))
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
        secret_args = {
            'name': secret_doc['metadata']['name'],
            'secret_type': secret_type,
            'payload': payload
        }

        LOG.info('Storing encrypted data in Barbican for document [{}, {}]'
                 .format(secret_doc.schema, secret_doc.name))
        for i in range(CONF.secret_create_attempts):
            LOG.debug('Creating secret in Barbican, attempt {} of {}'
                      .format((i + 1), CONF.secret_create_attempts))
            try:
                return self._do_create_secret(secret_args)
            except Exception:
                if i == (CONF.secret_create_attempts - 1):
                    # This was the last attempt, re-raise any error
                    raise
                else:
                    # This was not the last attempt, suppress the error and
                    # try again after a brief sleep
                    sleep_amount = (i + 1)
                    LOG.error('Caught an error while trying to create a '
                              'secret in Barbican, will try again in {} second'
                              .format(sleep_amount))
                    time.sleep(sleep_amount)

    def _do_create_secret(self, secret_args):
        """Using the cache construct, and the barbican client, create a secret

        :param secret_args: Dict containing the data for the secret to create
        :type secret_args: dict
        :returns: Secret reference returned by Barbican
        :rtype: str
        """
        try:
            return cache.lookup_by_payload(self.barbicanclient,
                                           **secret_args)
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPClientError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanClientException(code=e.status_code,
                                                 details=str(e))
        except barbicanclient.exceptions.HTTPServerError as e:
            LOG.error('Caught %s error from Barbican, likely due to a '
                      'configuration or deployment issue.',
                      e.__class__.__name__)
            raise errors.BarbicanServerException(details=str(e))
        except barbicanclient.exceptions.PayloadException as e:
            LOG.error('Caught %s error from Barbican, because the secret '
                      'payload type is unsupported.', e.__class__.__name__)
            raise errors.BarbicanServerException(details=str(e))

    def _base64_decode_payload(self, payload):
        # If the secret_type is 'opaque' then this implies the
        # payload was encoded to base64 previously. Reverse the
        # operation.
        try:
            return ast.literal_eval(base64.decode_as_text(payload))
        except Exception:
            with excutils.save_and_reraise_exception():
                message = ('Failed to unencode the original payload that '
                           'presumably was encoded to base64 with '
                           'secret_type: opaque.')
                LOG.error(message)

    def get_secret(self, secret_ref, src_doc):
        """Get a secret."""
        try:
            secret = cache.lookup_by_ref(self.barbicanclient, secret_ref)
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPClientError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanClientException(code=e.status_code,
                                                 details=str(e))
        except (barbicanclient.exceptions.HTTPServerError,
                ValueError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanServerException(details=str(e))

        payload = secret.payload
        if secret.secret_type == 'opaque':  # nosec
            LOG.debug('Base64-decoding original payload '
                      'for document [%s, %s] %s.', *src_doc.meta)
            secret = self._base64_decode_payload(payload)
        else:
            secret = payload

        return secret

    def delete_secret(self, secret_ref):
        """Delete a secret."""
        try:
            # NOTE(felipemonteiro): No cache invalidation is performed here
            # as the only API that invokes this method is DELETE /revisions
            # which also invalidates the entire Barbican cache.
            return self.barbicanclient.call("secrets.delete", secret_ref)
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPServerError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanClientException(details=str(e))
        except barbicanclient.exceptions.HTTPClientError as e:
            if e.status_code == 404:
                LOG.warning('Could not delete secret %s because it was not '
                            'found. Assuming it no longer exists.', secret_ref)
            raise
