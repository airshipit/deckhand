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

from oslo_config import cfg
from oslo_context import context

CONF = cfg.CONF


class RequestContext(context.RequestContext):
    """User security context object

    Stores information about the security context under which the user
    accesses the system, as well as additional request information.
    """

    def __init__(self, project=None, **kwargs):
        if project:
            kwargs['tenant'] = project
        self.project = project
        super(RequestContext, self).__init__(**kwargs)

    def to_dict(self):
        out_dict = super(RequestContext, self).to_dict()
        out_dict['roles'] = self.roles

        if out_dict.get('tenant'):
            out_dict['project'] = out_dict['tenant']
            out_dict.pop('tenant')
        return out_dict

    @classmethod
    def from_dict(cls, values):
        return cls(**values)


def get_context():
    """A helper method to get a blank context (useful for tests)."""
    return RequestContext(user_id=None,
                          project_id=None,
                          roles=[],
                          is_admin=False,
                          overwrite=False)
