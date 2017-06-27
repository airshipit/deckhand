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

from deckhand.control import base as api_base


class SecretsResource(api_base.BaseResource):
    """API resource for interacting with Barbican.

    TODO(felipemonteiro): Once Barbican integration is fully implemented,
    implement API endpoints below.
    """

    def __init__(self, **kwargs):
        super(SecretsResource, self).__init__(**kwargs)
        self.authorized_roles = ['user']

    def on_get(self, req, resp):
        # TODO(felipemonteiro): Implement this API endpoint.
        resp.body = json.dumps({'secrets': 'test_secrets'})
        resp.status = falcon.HTTP_200
