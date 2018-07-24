# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from oslo_log import log as logging

from deckhand.conf import config

CONF = config.CONF
LOG = logging.getLogger(__name__)

_CACHE_OPTS = {
    'cache.type': 'memory',
    'expire': CONF.barbican.cache_timeout,
}
_CACHE = CacheManager(**parse_cache_config_options(_CACHE_OPTS))
_BARBICAN_CACHE = _CACHE.get_cache('barbican_cache')


# NOTE(felipemonteiro): The functions below realize a lookup and reverse-lookup
# to allow for much faster retrieval of encrypted data from Barbican, which
# doesn't currently support batched requests in its Secrets API. This behavior
# is necessary since Deckhand has to potentially retrieve and store up to
# dozens of secrets per request. Note that data for both lookup functions
# below are invalidated together, as they are tied to the same cache.

def lookup_by_ref(barbicanclient, secret_ref):
    """Look up secret object using secret reference.

    Allows for quick lookup of secret payloads using ``secret_ref`` via
    caching.
    """
    def do_lookup():
        """Returns secret object stored in Barbican."""
        return barbicanclient.call("secrets.get", secret_ref)

    if CONF.barbican.enable_cache:
        return _BARBICAN_CACHE.get(key=secret_ref, createfunc=do_lookup)
    else:
        return do_lookup()


def lookup_by_payload(barbicanclient, **kwargs):
    """Look up secret reference using the secret payload.

    Allows for quick lookup of secret references using ``secret_payload`` via
    caching (essentially a reverse-lookup).

    Useful for ensuring that documents with the same secret payload (which
    occurs when the same document is recreated across different revisions)
    persist the same secret reference in the database -- and thus quicker
    future ``lookup_by_ref`` lookups.
    """
    def do_lookup():
        """Returns secret Barbican reference."""
        secret = barbicanclient.call("secrets.create", **kwargs)
        return secret.store()

    secret_payload = kwargs['payload']

    if CONF.barbican.enable_cache:
        return _BARBICAN_CACHE.get(key=secret_payload, createfunc=do_lookup)
    else:
        return do_lookup()


def invalidate():
    _BARBICAN_CACHE.clear()
