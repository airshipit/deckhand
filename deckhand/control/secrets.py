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

import falcon

from oslo_serialization import jsonutils as json

from deckhand.barbican import driver
from deckhand.control import base as api_base


class SecretsResource(api_base.BaseResource):
    """API resource for interacting with Barbican.

    NOTE: Currently only supports Barbican.
    """

    def __init__(self, **kwargs):
        super(SecretsResource, self).__init__(**kwargs)
        self.authorized_roles = ['user']
        self.barbican_driver = driver.BarbicanDriver()

    def on_post(self, req, resp):
        """Create a secret.

        :param name: The name of the secret. Required.
        :param type: The type of the secret. Optional.

        For a list of types, please refer to the following API documentation:
        https://docs.openstack.org/barbican/latest/api/reference/secret_types.html
        """
        secret_name = req.params.get('name')
        secret_type = req.params.get('type')

        if not secret_name:
            resp.status = falcon.HTTP_400

        # Do not allow users to call Barbican with all permitted kwargs.
        # Selectively include only what we allow.
        kwargs = {'name': secret_name, 'secret_type': secret_type}
        secret = self.barbican_driver.create_secret(**kwargs)

        resp.body = json.dumps(secret)
        resp.status = falcon.HTTP_200
