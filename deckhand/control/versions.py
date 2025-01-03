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

from deckhand.common import utils
from deckhand.control import base as api_base


class VersionsResource(api_base.BaseResource):
    """Versions resource

    Returns the list of supported versions of the Deckhand API.
    Unauthenticated GET.
    """
    no_authentication_methods = ['GET']

    def on_get(self, req, resp):
        resp_body = {
            'v1.0': {
                'path': '/api/v1.0',
                'status': 'stable'
            }
        }
        resp.text = utils.safe_yaml_dump(resp_body)
        resp.status = falcon.HTTP_200
