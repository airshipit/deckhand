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

"""RequestContext: context for requests that persist throughout Deckhand."""

import copy

from oslo_context import context
from oslo_db.sqlalchemy import enginefacade
from oslo_utils import timeutils
import six


@enginefacade.transaction_context_provider
class RequestContext(context.RequestContext):
    """Security context and request information.

    Represents the user taking a given action within the system.

    """

    def __init__(self, user_id=None, is_admin=None, user_name=None,
                 timestamp=None, **kwargs):
        if user_id:
            kwargs['user'] = user_id

        super(RequestContext, self).__init__(is_admin=is_admin, **kwargs)

        if not timestamp:
            timestamp = timeutils.utcnow()
        if isinstance(timestamp, six.string_types):
            timestamp = timeutils.parse_strtime(timestamp)
        self.timestamp = timestamp

    @property
    def project_id(self):
        return self.tenant

    @project_id.setter
    def project_id(self, value):
        self.tenant = value

    @property
    def user_id(self):
        return self.user

    @user_id.setter
    def user_id(self, value):
        self.user = value

    def to_dict(self):
        values = super(RequestContext, self).to_dict()
        values.update({
            'user_id': getattr(self, 'user_id', None),
            'project_id': getattr(self, 'project_id', None),
            'is_admin': getattr(self, 'is_admin', None)
        })
        return values

    @classmethod
    def from_dict(cls, values):
        return super(RequestContext, cls).from_dict(
            values,
            user_id=values.get('user_id'),
            project_id=values.get('project_id')
        )

    def elevated(self, read_deleted=None):
        """Return a version of this context with admin flag set."""
        context = copy.copy(self)
        # context.roles must be deepcopied to leave original roles
        # without changes
        context.roles = copy.deepcopy(self.roles)
        context.is_admin = True

        if 'admin' not in context.roles:
            context.roles.append('admin')

        if read_deleted is not None:
            context.read_deleted = read_deleted

        return context

    def to_policy_values(self):
        policy = super(RequestContext, self).to_policy_values()
        policy['is_admin'] = self.is_admin
        return policy

    def __str__(self):
        return "<Context %s>" % self.to_dict()
