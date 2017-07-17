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

import datetime

from oslo_versionedobjects import base
from oslo_versionedobjects import fields as obj_fields

from deckhand import objects


class DeckhandObjectRegistry(base.VersionedObjectRegistry):

    # Steal this from Cinder to bring all registered objects
    # into the Deckhand_provisioner.objects namespace.
    def registration_hook(self, cls, index):
        setattr(objects, cls.obj_name(), cls)


class DeckhandObject(base.VersionedObject):

    # Version 1.0: Initial version
    VERSION = '1.0'

    OBJ_PROJECT_NAMESPACE = 'deckhand.objects'

    def obj_load_attr(self, attrname):
        if attrname in self.fields.keys():
            setattr(self, attrname, None)
        else:
            raise ValueError("Unknown field %s." % (attrname))

    def obj_to_simple(self):
        """
        Create a simple primitive representation of this object excluding
        all the versioning stuff. Used to serialize an object for public
        consumption, not intended to be deserialized by OVO.
        """

        primitive = dict()

        primitive['model_type'] = self.__class__.__name__
        primitive['model_version'] = self.VERSION

        for name, field in self.fields.items():
            if self.obj_attr_is_set(name):
                value = getattr(self, name)
                if (hasattr(value, 'obj_to_simple') and
                    callable(value.obj_to_simple)):
                    primitive[name] = value.obj_to_simple()
                else:
                    value = field.to_primitive(self, name, value)
                    if value is not None:
                        primitive[name] = value

        return primitive


class DeckhandPersistentObject(base.VersionedObject):

    fields = {
        'created_at': obj_fields.DateTimeField(nullable=False),
        'created_by': obj_fields.StringField(nullable=False),
        'updated_at': obj_fields.DateTimeField(nullable=True),
        'updated_by': obj_fields.StringField(nullable=True),
    }

    def set_create_fields(self, context):
        self.created_at = datetime.datetime.now()
        self.created_by = context.user

    def set_update_fields(self, context):
        self.updated_at = datetime.datetime.now()
        self.updated_by = context.user
