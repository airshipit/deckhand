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

from deckhand import context


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


class DeckhandRequest(falcon.Request):
    context_type = context.RequestContext

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
