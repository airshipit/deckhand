# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack Foundation
# Copyright 2011 Piston Cloud Computing, Inc.
# Copyright 2017 AT&T Intellectual Property.
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Deckhand Client interface. Handles the REST calls and responses.
"""

from keystoneauth1 import adapter
from keystoneauth1 import identity
from keystoneauth1 import session as ksession
from oslo_log import log as logging

from deckhand.client import buckets
from deckhand.client import exceptions
from deckhand.client import revisions
from deckhand.client import tags
from deckhand.client import validations


class SessionClient(adapter.Adapter):
    """Wrapper around ``keystoneauth1`` client session implementation and used
    internally by :class:`Client` below.

    Injects Deckhand-specific YAML headers necessary for communication with the
    Deckhand API.
    """

    client_name = 'python-deckhandclient'
    client_version = '1.0'

    def __init__(self, *args, **kwargs):
        self.api_version = kwargs.pop('api_version', None)
        super(SessionClient, self).__init__(*args, **kwargs)

    def request(self, url, method, **kwargs):
        kwargs.setdefault('headers', kwargs.get('headers', {}))
        kwargs['headers']['Accept'] = 'application/x-yaml'
        kwargs['headers']['Content-Type'] = 'application/x-yaml'

        raise_exc = kwargs.pop('raise_exc', True)
        kwargs['data'] = kwargs.pop('body', None)
        resp = super(SessionClient, self).request(url, method, raise_exc=False,
                                                  **kwargs)
        body = resp.content

        if raise_exc and resp.status_code >= 400:
            raise exceptions.from_response(resp, body, url, method)

        return resp, body


def _construct_http_client(api_version=None,
                           auth=None,
                           auth_token=None,
                           auth_url=None,
                           cacert=None,
                           cert=None,
                           endpoint_override=None,
                           endpoint_type='publicURL',
                           http_log_debug=False,
                           insecure=False,
                           logger=None,
                           password=None,
                           project_domain_id=None,
                           project_domain_name=None,
                           project_id=None,
                           project_name=None,
                           region_name=None,
                           service_name=None,
                           service_type='deckhand',
                           session=None,
                           timeout=None,
                           user_agent='python-deckhandclient',
                           user_domain_id=None,
                           user_domain_name=None,
                           user_id=None,
                           username=None,
                           **kwargs):
    if not session:
        if not auth and auth_token:
            auth = identity.Token(auth_url=auth_url,
                                  token=auth_token,
                                  project_id=project_id,
                                  project_name=project_name,
                                  project_domain_id=project_domain_id,
                                  project_domain_name=project_domain_name)
        elif not auth:
            auth = identity.Password(username=username,
                                     user_id=user_id,
                                     password=password,
                                     project_id=project_id,
                                     project_name=project_name,
                                     auth_url=auth_url,
                                     project_domain_id=project_domain_id,
                                     project_domain_name=project_domain_name,
                                     user_domain_id=user_domain_id,
                                     user_domain_name=user_domain_name)
        session = ksession.Session(auth=auth,
                                   verify=(cacert or not insecure),
                                   timeout=timeout,
                                   cert=cert,
                                   user_agent=user_agent)

    return SessionClient(api_version=api_version,
                         auth=auth,
                         endpoint_override=endpoint_override,
                         interface=endpoint_type,
                         logger=logger,
                         region_name=region_name,
                         service_name=service_name,
                         service_type=service_type,
                         session=session,
                         user_agent=user_agent,
                         **kwargs)


class Client(object):
    """Top-level object to access the Deckhand API."""

    def __init__(self,
                 api_version=None,
                 auth=None,
                 auth_token=None,
                 auth_url=None,
                 cacert=None,
                 cert=None,
                 direct_use=True,
                 endpoint_override=None,
                 endpoint_type='publicURL',
                 http_log_debug=False,
                 insecure=False,
                 logger=None,
                 password=None,
                 project_domain_id=None,
                 project_domain_name=None,
                 project_id=None,
                 project_name=None,
                 region_name=None,
                 service_name=None,
                 service_type='deckhand',
                 session=None,
                 timeout=None,
                 user_domain_id=None,
                 user_domain_name=None,
                 user_id=None,
                 username=None,
                 **kwargs):
        """Initialization of Client object.

        :param api_version: Compute API version
        :type api_version: novaclient.api_versions.APIVersion
        :param str auth: Auth
        :param str auth_token: Auth token
        :param str auth_url: Auth URL
        :param str cacert: ca-certificate
        :param str cert: certificate
        :param bool direct_use: Inner variable of novaclient. Do not use it
            outside novaclient. It's restricted.
        :param str endpoint_override: Bypass URL
        :param str endpoint_type: Endpoint Type
        :param bool http_log_debug: Enable debugging for HTTP connections
        :param bool insecure: Allow insecure
        :param logging.Logger logger: Logger instance to be used for all
            logging stuff
        :param str password: User password
        :param str project_domain_id: ID of project domain
        :param str project_domain_name: Name of project domain
        :param str project_id: Project/Tenant ID
        :param str project_name: Project/Tenant name
        :param str region_name: Region Name
        :param str service_name: Service Name
        :param str service_type: Service Type
        :param str session: Session
        :param float timeout: API timeout, None or 0 disables
        :param str user_domain_id: ID of user domain
        :param str user_domain_name: Name of user domain
        :param str user_id: User ID
        :param str username: Username
        """

        self.project_id = project_id
        self.project_name = project_name
        self.user_id = user_id

        self.logger = logger or logging.getLogger(__name__)

        self.buckets = buckets.BucketManager(self)
        self.revisions = revisions.RevisionManager(self)
        self.tags = tags.RevisionTagManager(self)
        self.validations = validations.ValidationManager(self)

        self.client = _construct_http_client(
            api_version=api_version,
            auth=auth,
            auth_token=auth_token,
            auth_url=auth_url,
            cacert=cacert,
            cert=cert,
            endpoint_override=endpoint_override,
            endpoint_type=endpoint_type,
            http_log_debug=http_log_debug,
            insecure=insecure,
            logger=self.logger,
            password=password,
            project_domain_id=project_domain_id,
            project_domain_name=project_domain_name,
            project_id=project_id,
            project_name=project_name,
            region_name=region_name,
            service_name=service_name,
            service_type=service_type,
            session=session,
            timeout=timeout,
            user_domain_id=user_domain_id,
            user_domain_name=user_domain_name,
            user_id=user_id,
            username=username,
            **kwargs)

    @property
    def api_version(self):
        return self.client.api_version

    @api_version.setter
    def api_version(self, value):
        self.client.api_version = value

    @property
    def projectid(self):
        self.logger.warning(_("Property 'projectid' is deprecated since "
                              "Ocata. Use 'project_name' instead."))
        return self.project_name

    @property
    def tenant_id(self):
        self.logger.warning(_("Property 'tenant_id' is deprecated since "
                              "Ocata. Use 'project_id' instead."))
        return self.project_id
