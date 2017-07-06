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

from keystoneauth1.identity import v3
from keystoneauth1 import session

from deckhand.conf import config
from deckhand import errors

from barbicanclient import barbican
from barbicanclient import exceptions as barbican_exc

CONF = config.CONF


class BarbicanClientWrapper(object):
    """Barbican client wrapper class that encapsulates authentication logic."""

    def __init__(self):
        """Initialise the BarbicanClientWrapper for use."""
        self._cached_client = None

    def _invalidate_cached_client(self):
        """Tell the wrapper to invalidate the cached barbican-client."""
        self._cached_client = None

    def _get_client(self, retry_on_conflict=True):
        # If we've already constructed a valid, authed client, just return
        # that.
        if retry_on_conflict and self._cached_client is not None:
            return self._cached_client

        # TODO: Deckhand's configuration file needs to be populated with
        # correct Keysone authentication values as well as the Barbican
        # endpoint URL automatically.
        barbican_url = (CONF.barbican.api_endpoint
                        if CONF.barbican.api_endpoint
                        else 'http://127.0.0.1:9311')

        keystone_auth = dict(CONF.keystone_authtoken)
        auth = v3.Password(**keystone_auth)
        sess = session.Session(auth=auth)

        try:
            # TODO: replace with ``barbican_url``.
            cli = barbican.client.Client(endpoint=barbican_url,
                                         session=sess)
            # Cache the client so we don't have to reconstruct and
            # reauthenticate it every time we need it.
            if retry_on_conflict:
                self._cached_client = cli

        except barbican_exc.HTTPAuthError:
            msg = _("Unable to authenticate Barbican client.")
            # TODO: Log the error.
            raise errors.ApiError(msg)

        return cli

    def _multi_getattr(self, obj, attr):
        """Support nested attribute path for getattr().

        :param obj: Root object.
        :param attr: Path of final attribute to get. E.g., "a.b.c.d"

        :returns: The value of the final named attribute.
        :raises: AttributeError will be raised if the path is invalid.
        """
        for attribute in attr.split("."):
            obj = getattr(obj, attribute)
        return obj

    def call(self, method, *args, **kwargs):
        """Call a barbican client method and retry on stale token.

        :param method: Name of the client method to call as a string.
        :param args: Client method arguments.
        :param kwargs: Client method keyword arguments.
        :param retry_on_conflict: Boolean value. Whether the request should be
                                  retried in case of a conflict error
                                  (HTTP 409) or not. If retry_on_conflict is
                                  False the cached instance of the client
                                  won't be used. Defaults to True.
        """
        retry_on_conflict = kwargs.pop('retry_on_conflict', True)

        for attempt in range(2):
            client = self._get_client(retry_on_conflict=retry_on_conflict)

            try:
                return self._multi_getattr(client, method)(*args, **kwargs)
            except barbican_exc.HTTPAuthError:
                # In this case, the authorization token of the cached
                # barbican-client probably expired. So invalidate the cached
                # client and the next try will start with a fresh one.
                if not attempt:
                    self._invalidate_cached_client()
                    # TODO: include after implementing oslo.log.
                    # LOG.debug("The Barbican client became unauthorized. "
                    #           "Will attempt to reauthorize and try again.")
                else:
                    # This code should be unreachable actually
                    raise
