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

import barbicanclient
from oslo_log import log as logging

from deckhand.barbican import client_wrapper
from deckhand import errors
from deckhand import utils

LOG = logging.getLogger(__name__)


class BarbicanDriver(object):

    def __init__(self):
        self.barbicanclient = client_wrapper.BarbicanClientWrapper()

    def create_secret(self, **kwargs):
        """Create a secret."""
        secret = self.barbicanclient.call("secrets.create", **kwargs)

        try:
            secret_ref = secret.store()
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPClientError,
                barbicanclient.exceptions.HTTPServerError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanException(details=str(e))

        # NOTE(fmontei): The dictionary representation of the Secret object by
        # default has keys that are not snake case -- so make them snake case.
        resp = secret.to_dict()
        for key in resp:
            resp[utils.to_snake_case(key)] = resp.pop(key)
        resp['secret_ref'] = secret_ref
        return resp

    def get_secret(self, secret_ref):
        """Get a secret."""

        try:
            return self.barbicanclient.call("secrets.get", secret_ref)
        except (barbicanclient.exceptions.HTTPAuthError,
                barbicanclient.exceptions.HTTPClientError,
                barbicanclient.exceptions.HTTPServerError) as e:
            LOG.exception(str(e))
            raise errors.BarbicanException(details=str(e))
