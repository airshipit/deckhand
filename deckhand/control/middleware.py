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
from oslo_config import cfg
from oslo_log import log as logging
import six

import deckhand.context
from deckhand import errors

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class ContextMiddleware(object):

    def process_resource(self, req, resp, resource, params):
        """Handle the authentication needs of the routed request.

        :param req: ``falcon`` request object that will be examined for method
        :param resource: ``falcon`` resource class that will be examined for
            authentication needs by looking at the no_authentication_methods
            list of http methods. By default, this will assume that all
            requests need authentication unless noted in this array.
            Note that this does not bypass any authorization checks, which will
            fail if the user is not authenticated.
        :raises: falcon.HTTPUnauthorized: when value of the
            'X-Identity-Status' header is not 'Confirmed' and anonymous access
            is disallowed.
        """
        authentication_required = True
        try:
            if req.method in resource.no_authentication_methods:
                authentication_required = False
        except AttributeError:
            # assume that authentication is required.
            pass
        if authentication_required:
            if req.headers.get('X-IDENTITY-STATUS') == 'Confirmed':
                req.context = deckhand.context.RequestContext.from_environ(
                    req.env)
            elif CONF.development_mode:
                req.context = deckhand.context.get_context()
            else:
                raise falcon.HTTPUnauthorized()
        else:
            req.context = deckhand.context.RequestContext.from_environ(req.env)
        # set transaction correlation fields in context
        req.context.end_user = req.headers.get('X-END-USER')
        req.context.context_marker = req.headers.get('X-CONTEXT-MARKER')


class HookableMiddlewareMixin(object):
    """Provides methods to extract before and after hooks from WSGI Middleware
    Prior to falcon 0.2.0b1, it's necessary to provide falcon with middleware
    as "hook" functions that are either invoked before (to process requests)
    or after (to process responses) the API endpoint code runs.
    This mixin allows the process_request and process_response methods from a
    typical WSGI middleware object to be extracted for use as these hooks, with
    the appropriate method signatures.
    """

    def as_before_hook(self):
        """Extract process_request method as "before" hook
        :return: before hook function
        """

        # Need to wrap this up in a closure because the parameter counts
        # differ
        def before_hook(req, resp, params=None):
            return self.process_request(req, resp)

        try:
            return before_hook
        except AttributeError as ex:
            # No such method, we presume.
            message_template = ("Failed to get before hook from middleware "
                                "{0} - {1}")
            message = message_template.format(self.__name__, ex.message)
            LOG.error(message)
            raise errors.DeckhandException(message)

    def as_after_hook(self):
        """Extract process_response method as "after" hook
        :return: after hook function
        """

        # Need to wrap this up in a closure because the parameter counts
        # differ
        def after_hook(req, resp, resource=None):
            return self.process_response(req, resp, resource)

        try:
            return after_hook
        except AttributeError as ex:
            # No such method, we presume.
            message_template = ("Failed to get after hook from middleware "
                                "{0} - {1}")
            message = message_template.format(self.__name__, ex.message)
            LOG.error(message)
            raise errors.DeckhandException(message)


class YAMLTranslator(HookableMiddlewareMixin, object):
    """Middleware for converting all responses (error and success) to YAML.

    ``falcon`` error exceptions use JSON formatting and headers by default.
    This middleware will intercept all responses and guarantee they are YAML
    format.

    .. note::

        This does not include the 401 Unauthorized that is raised by
        ``keystonemiddleware`` which is executed in the pipeline before
        ``falcon`` middleware.
    """

    def process_request(self, req, resp):
        """Performs content type enforcement on behalf of REST verbs."""
        valid_content_types = ['application/x-yaml']

        # GET and DELETE should never carry a message body, and have
        # no content type. Check for content-length or
        # transfer-encoding to determine if a content-type header
        # is required.
        requires_content_type = (
            req.method not in ['GET', 'DELETE'] and (
                (req.content_length is not None and
                 req.content_length > 0) or
                req.get_header('transfer-encoding') is not None
            )
        )

        if requires_content_type:
            content_type = (req.content_type.split(';', 1)[0].strip()
                            if req.content_type else '')

            if not content_type:
                raise falcon.HTTPMissingHeader('Content-Type')
            elif content_type not in valid_content_types:
                message = (
                    "Unexpected content type: {type}. Expected content types "
                    "are: {expected}."
                ).format(
                    type=six.b(req.content_type).decode('utf-8'),
                    expected=valid_content_types
                )
                raise falcon.HTTPUnsupportedMediaType(description=message)

    def process_response(self, req, resp, resource, req_succeeded):
        """Converts responses to ``application/x-yaml`` content type."""
        if resp.status != '204 No Content':
            resp.set_header('Content-Type', 'application/x-yaml')

        kwargs = {
            "explicit_start": True,
            "explicit_end": True
        }

        for attr in ('body', 'data'):
            if not hasattr(resp, attr):
                continue

            resp_attr = getattr(resp, attr)

            if isinstance(resp_attr, dict):
                setattr(resp, attr, yaml.safe_dump(resp_attr, **kwargs))
            elif isinstance(resp_attr, (list, tuple)):
                setattr(resp, attr, yaml.safe_dump_all(resp_attr, **kwargs))


class LoggingMiddleware(object):
    def process_resource(self, req, resp, resource, params):
        # don't log health checks
        if not req.url.endswith('/health'):
            LOG.info(
                "Request: %s %s %s",
                req.method,
                req.uri,
                req.query_string)

    def process_response(self, req, resp, resource, req_succeeded):
        ctx = req.context
        # only log health check responses if the check failed
        if req.url.endswith('/health'):
            resp_code = self._get_resp_code(resp)
            if not resp_code == 204:
                LOG.error(
                    'Health check has failed with response status %s',
                    resp.status)
        else:
            context_marker = getattr(ctx, 'context_marker', None)
            request_id = getattr(ctx, 'request_id', None)
            user = getattr(ctx, 'user', None)
            end_user = getattr(ctx, 'end_user', None)
            if context_marker is not None:
                resp.append_header('X-Context-Marker', context_marker)
            if request_id is not None:
                resp.append_header('X-Deckhand-Req', request_id)
            if end_user is not None:
                resp.append_header('X-End-User', end_user)
            if user is not None:
                resp.append_header('X-User-Name', user)
            LOG.info(
                "Response: %s %s %s",
                req.method,
                req.uri,
                resp.status)

    def _get_resp_code(self, resp):
        # Falcon response object doesn't have a raw status code.
        # Splits by the first space
        try:
            return int(resp.status.split(" ", 1)[0])
        except ValueError:
            # if for some reason this Falcon response doesn't have a valid
            # status, return a high value sentinel
            return 9999
