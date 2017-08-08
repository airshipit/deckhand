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

import yaml

import falcon
from oslo_context import context
from oslo_log import log as logging
from oslo_serialization import jsonutils as json
import six

LOG = logging.getLogger(__name__)


class BaseResource(object):
    """Base resource class for implementing API resources."""

    def on_options(self, req, resp):
        self_attrs = dir(self)
        methods = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH']
        allowed_methods = []

        for m in methods:
            if 'on_' + m.lower() in self_attrs:
                allowed_methods.append(m)

        resp.headers['Allow'] = ','.join(allowed_methods)
        resp.status = falcon.HTTP_200

    def return_error(self, resp, status_code, message="", retry=False):
        resp.body = json.dumps(
            {'type': 'error', 'message': six.text_type(message),
             'retry': retry})
        resp.status = status_code

    def to_yaml_body(self, dict_body):
        """Converts JSON body into YAML response body.

        :dict_body: response body to be converted to YAML.
        :returns: YAML encoding of `dict_body`.
        """
        if isinstance(dict_body, dict):
            return yaml.safe_dump(dict_body)
        elif isinstance(dict_body, list):
            return yaml.safe_dump_all(dict_body)
        raise TypeError('Unrecognized dict_body type when converting response '
                        'body to YAML format.')


class DeckhandRequest(falcon.Request):

    def __init__(self, env, options=None):
        super(DeckhandRequest, self).__init__(env, options)
        self.context = context.RequestContext.from_environ(self.env)

    @property
    def project_id(self):
        return self.context.tenant

    @property
    def user_id(self):
        return self.context.user

    @property
    def roles(self):
        return self.context.roles

    def __repr__(self):
        return '%s, context=%s' % (self.path, self.context)
