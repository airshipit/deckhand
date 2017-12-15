# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack Foundation
# Copyright 2017 AT&T Intellectual Property.
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
Base utilities to build API operation managers and objects on top of.
"""

import copy
import yaml

from oslo_utils import strutils
import six
from six.moves.urllib import parse


def getid(obj):
    """Get object's ID or object.

    Abstracts the common pattern of allowing both an object or an object's ID
    as a parameter when dealing with relationships.
    """
    try:
        return obj.id
    except AttributeError:
        return obj


def prepare_query_string(params):
    """Convert dict params to query string"""
    # Transform the dict to a sequence of two-element tuples in fixed
    # order, then the encoded string will be consistent in Python 2&3.
    if not params:
        return ''
    params = sorted(params.items(), key=lambda x: x[0])
    return '?%s' % parse.urlencode(params) if params else ''


def get_url_with_filter(url, filters):
    query_string = prepare_query_string(filters)
    url = "%s%s" % (url, query_string)
    return url


class Resource(object):
    """Base class for OpenStack resources (tenant, user, etc.).

    This is pretty much just a bag for attributes.
    """

    HUMAN_ID = False
    NAME_ATTR = 'name'

    def __init__(self, manager, info, loaded=False):
        """Populate and bind to a manager.

        :param manager: BaseManager object
        :param info: dictionary representing resource attributes
        :param loaded: prevent lazy-loading if set to True
        :param resp: Response or list of Response objects
        """
        self.manager = manager
        self._info = info or {}
        self._add_details(info)
        self._loaded = loaded

    def __repr__(self):
        reprkeys = sorted(k
                          for k in self.__dict__.keys()
                          if k[0] != '_' and k != 'manager')
        info = ", ".join("%s=%s" % (k, getattr(self, k)) for k in reprkeys)
        return "<%s %s>" % (self.__class__.__name__, info)

    @property
    def api_version(self):
        return self.manager.api_version

    @property
    def human_id(self):
        """Human-readable ID which can be used for bash completion.
        """
        if self.HUMAN_ID:
            name = getattr(self, self.NAME_ATTR, None)
            if name is not None:
                return strutils.to_slug(name)
        return None

    def _add_details(self, info):
        for (k, v) in info.items():
            try:
                setattr(self, k, v)
                self._info[k] = v
            except AttributeError:
                # In this case we already defined the attribute on the class
                pass

    def __getattr__(self, k):
        if k not in self.__dict__:
            # NOTE(bcwaldon): disallow lazy-loading if already loaded once
            if not self.is_loaded():
                self.get()
                return self.__getattr__(k)

            raise AttributeError(k)
        else:
            return self.__dict__[k]

    def get(self):
        """Support for lazy loading details.

        Some clients, such as novaclient have the option to lazy load the
        details, details which can be loaded with this function.
        """
        # set_loaded() first ... so if we have to bail, we know we tried.
        self.set_loaded(True)
        if not hasattr(self.manager, 'get'):
            return

        new = self.manager.get(self.id)
        if new:
            self._add_details(new._info)

    def __eq__(self, other):
        if not isinstance(other, Resource):
            return NotImplemented
        # two resources of different types are not equal
        if not isinstance(other, self.__class__):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return self._info == other._info

    def __ne__(self, other):
        # Using not of '==' implementation because the not of
        # __eq__, when it returns NotImplemented, is returning False.
        return not self == other

    def is_loaded(self):
        return self._loaded

    def set_loaded(self, val):
        self._loaded = val

    def set_info(self, key, value):
        self._info[key] = value

    def to_dict(self):
        return copy.deepcopy(self._info)


class Manager(object):
    """Manager for API service.

    Managers interact with a particular type of API (buckets, revisions, etc.)
    and provide CRUD operations for them.
    """
    resource_class = None

    def __init__(self, api):
        self.api = api

    @property
    def client(self):
        return self.api.client

    @property
    def api_version(self):
        return self.api.api_version

    def _to_dict(self, body, many=False):
        """Convert YAML-formatted response body into dict or list.

        :param body: YAML-formatted response body to convert.
        :param many: Controls whether to return list or dict. If True, returns
            list, else dict. False by default.
        :rtype: dict or list
        """
        try:
            return (
                list(yaml.safe_load_all(body))
                    if many else yaml.safe_load(body)
            )
        except yaml.YAMLError:
            return None

    def _list(self, url, response_key=None, obj_class=None, body=None,
              filters=None):
        if filters:
            url = get_url_with_filter(url, filters)
        if body:
            resp, body = self.api.client.post(url, body=body)
        else:
            resp, body = self.api.client.get(url)
        body = self._to_dict(body, many=True)

        if obj_class is None:
            obj_class = self.resource_class

        if response_key is not None:
            data = body[response_key]
        else:
            data = body

        items = [obj_class(self, res, loaded=True)
                 for res in data if res]
        return items

    def _get(self, url, response_key=None, filters=None):
        if filters:
            url = get_url_with_filter(url, filters)
        resp, body = self.api.client.get(url)
        body = self._to_dict(body)

        if response_key is not None:
            content = body[response_key]
        else:
            content = body
        return self.resource_class(self, content, loaded=True)

    def _create(self, url, data, response_key=None):
        if isinstance(data, six.string_types):
            resp, body = self.api.client.post(url, body=data)
        else:
            resp, body = self.api.client.post(url, data=data)
        body = self._to_dict(body)

        if body:
            if response_key:
                return self.resource_class(self, body[response_key])
            else:
                return self.resource_class(self, body)
        else:
            return body

    def _delete(self, url):
        resp, body = self.api.client.delete(url)
        body = self._to_dict(body)
        return body

    def _update(self, url, data, response_key=None):
        if isinstance(data, six.string_types):
            resp, body = self.api.client.put(url, body=data)
        else:
            resp, body = self.api.client.put(url, data=data)
        body = self._to_dict(body)

        if body:
            if response_key:
                return self.resource_class(self, body[response_key])
            else:
                return self.resource_class(self, body)
        else:
            return body
