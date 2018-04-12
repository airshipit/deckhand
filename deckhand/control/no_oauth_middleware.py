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


class NoAuthFilter(object):
    """PasteDeploy filter for NoAuth to be used in testing."""

    def __init__(self, app, forged_roles=None):
        self.app = app
        self.forged_roles = forged_roles or ('admin',)

    def __call__(self, environ, start_response):
        """Forge headers to make unauthenticated requests look authenticated.

        If the request has a X-AUTH-TOKEN header,
        assume it is a valid request and
        noop. Otherwise forge Keystone middleware headers so the
        request looks valid
        with the configured forged roles.
        """
        if 'HTTP_X_AUTH_TOKEN' in environ:
            return self.app(environ, start_response)

        environ['HTTP_X_IDENTITY_STATUS'] = 'Confirmed'

        for envvar in [
                'USER_NAME', 'USER_ID', 'USER_DOMAIN_ID', 'PROJECT_ID',
                'PROJECT_DOMAIN_NAME'
        ]:
            varname = "HTTP_X_%s" % envvar
            environ[varname] = 'noauth'

        if 'admin' in self.forged_roles:
            environ['HTTP_X_IS_ADMIN_PROJECT'] = 'True'
        else:
            environ['HTTP_X_IS_ADMIN_PROJECT'] = 'False'
        environ['HTTP_X_ROLES'] = ','.join(self.forged_roles)

        return self.app(environ, start_response)


def noauth_filter_factory(global_conf, forged_roles):
    """Create a NoAuth paste deploy filter

    :param forged_roles: A space seperated list for roles to forge on requests
    """
    forged_roles = forged_roles.split()

    def filter(app):
        return NoAuthFilter(app, forged_roles)

    return filter
