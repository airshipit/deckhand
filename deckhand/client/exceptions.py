# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2017 AT&T Intellectual Property.
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
Exception definitions.
"""

import logging
import yaml

import six

LOG = logging.getLogger(__name__)


class ClientException(Exception):
    """The base exception class for all exceptions this library raises."""
    message = "Unknown Error"

    def __init__(self, code, url, method, message=None, details=None,
                 reason=None, apiVersion=None, retry=False, status=None,
                 kind=None, metadata=None):
        self.code = code
        self.url = url
        self.method = method
        self.message = message or self.__class__.message
        self.details = details
        self.reason = reason
        self.apiVersion = apiVersion
        self.retry = retry
        self.status = status
        self.kind = kind
        self.metadata = metadata

    def __str__(self):
        formatted_string = "%s (HTTP %s)" % (self.message, self.code)
        return formatted_string


class BadRequest(ClientException):
    """HTTP 400 - Bad request: you sent some malformed data."""
    http_status = 400
    message = "Bad request"


class Unauthorized(ClientException):
    """HTTP 401 - Unauthorized: bad credentials."""
    http_status = 401
    message = "Unauthorized"


class Forbidden(ClientException):
    """HTTP 403 - Forbidden: your credentials don't give you access to this
    resource.
    """
    http_status = 403
    message = "Forbidden"


class NotFound(ClientException):
    """HTTP 404 - Not found"""
    http_status = 404
    message = "Not found"


class MethodNotAllowed(ClientException):
    """HTTP 405 - Method Not Allowed"""
    http_status = 405
    message = "Method Not Allowed"


class Conflict(ClientException):
    """HTTP 409 - Conflict"""
    http_status = 409
    message = "Conflict"


# NotImplemented is a python keyword.
class HTTPNotImplemented(ClientException):
    """HTTP 501 - Not Implemented: the server does not support this operation.
    """
    http_status = 501
    message = "Not Implemented"


_code_map = dict((c.http_status, c)
                 for c in ClientException.__subclasses__())


def from_response(response, body, url, method=None):
    """Return an instance of a ``ClientException`` or subclass based on a
    request's response.
    """
    cls = _code_map.get(response.status_code, ClientException)

    try:
        kwargs = yaml.safe_load(body)
    except yaml.YAMLError as e:
        kwargs = None
        LOG.debug('Could not convert error from server into dict: %s',
                  six.text_type(e))

    if isinstance(kwargs, dict):
        kwargs.update({
            'code': response.status_code,
            'method': method,
            'url': url
        })
    else:
        kwargs = {
            'code': response.status_code,
            'method': method,
            'url': url,
            'message': response.text
        }

    return cls(**kwargs)
