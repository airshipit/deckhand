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

from oslo_log import log as logging
from oslo_versionedobjects import base
from oslo_versionedobjects import exception as ovo_exception
from oslo_versionedobjects import fields as ovo_fields

from deckhand import objects

LOG = logging.getLogger(__name__)


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
        'created_at': ovo_fields.DateTimeField(nullable=False),
        'created_by': ovo_fields.StringField(nullable=False),
        'updated_at': ovo_fields.DateTimeField(nullable=True),
        'updated_by': ovo_fields.StringField(nullable=True),
    }

    def set_create_fields(self, context):
        self.created_at = datetime.datetime.now()
        self.created_by = context.user

    def set_update_fields(self, context):
        self.updated_at = datetime.datetime.now()
        self.updated_by = context.user


class DeckhandPayloadBase(DeckhandPersistentObject):
    """Base class for the payload of versioned notifications."""
    # SCHEMA defines how to populate the payload fields. It is a dictionary
    # where every key value pair has the following format:
    # <payload_field_name>: (<data_source_name>,
    #                        <field_of_the_data_source>)
    # The <payload_field_name> is the name where the data will be stored in the
    # payload object, this field has to be defined as a field of the payload.
    # The <data_source_name> shall refer to name of the parameter passed as
    # kwarg to the payload's populate_schema() call and this object will be
    # used as the source of the data. The <field_of_the_data_source> shall be
    # a valid field of the passed argument.
    # The SCHEMA needs to be applied with the populate_schema() call before the
    # notification can be emitted.
    # The value of the payload.<payload_field_name> field will be set by the
    # <data_source_name>.<field_of_the_data_source> field. The
    # <data_source_name> will not be part of the payload object internal or
    # external representation.
    # Payload fields that are not set by the SCHEMA can be filled in the same
    # way as in any versioned object.
    SCHEMA = {}
    # Version 1.0: Initial version
    VERSION = '1.0'

    def __init__(self):
        super(DeckhandPayloadBase, self).__init__()
        self.populated = not self.SCHEMA

    def populate_schema(self, **kwargs):
        """Populate the object based on the SCHEMA and the source objects

        :param kwargs: A dict contains the source object at the key defined in
                       the SCHEMA
        """
        for key, (obj, field) in self.SCHEMA.items():
            source = kwargs[obj]
            if isinstance(source, dict):
                source = self._dict_to_obj(source)
            try:
                setattr(self, key, getattr(source, field))
            # ObjectActionError - not lazy loadable field
            # NotImplementedError - obj_load_attr() is not even defined
            # OrphanedObjectError - lazy loadable field but context is None
            except (#exception.ObjectActionError,
                    NotImplementedError,
                    #exception.OrphanedObjectError,
                    ovo_exception.OrphanedObjectError) as e:
                LOG.debug(("Defaulting the value of the field '%(field)s' "
                           "to None in %(payload)s due to '%(exception)s'"),
                          {'field': key,
                           'payload': self.__class__.__name__,
                           'exception': e})
                # NOTE: This will fail if the payload field is not
                # nullable, but that means that either the source object is not
                # properly initialized or the payload field needs to be defined
                # as nullable
                setattr(self, key, None)
        self.populated = True

        # the schema population will create changed fields but we don't need
        # this information in the notification
        self.obj_reset_changes(recursive=True)

    def _dict_to_obj(self, d):
        """Converts dictionary to object.

        :param d: The dictionary to convert into an object.
        :returns: The object representation of the dictionary passed in.
        """
        class Object:
            def __init__(self, **entries):
                self.__dict__.update(entries)

        return Object(**dict(d.items()))
