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
#
# Models for drydock_provisioner
#

import oslo_versionedobjects.fields as ovo_fields

import deckhand.objects as objects
import deckhand.objects.base as base
import deckhand.objects.fields as fields


class DocumentPayload(base.NotificationPayloadBase):
    SCHEMA = {
        'schema_version': ('document', 'schema_version'),
        'kind': ('document', 'uuid'),
        'metadata': ('document', 'name'),
        'data': ('document', 'hosts')
    }

    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'schema_version': fields.StringField(nullable=False),
        'kind': fields.StringField(nullable=False),
        'metadata': fields.DictOfStringsField(nullable=False),
        'data': fields.DictOfStringsField(nullable=False)
    }

    def __init__(self, document):
        super(DocumentPayload, self).__init__()
        self.populate_schema(document=document)


@base.DeckhandObjectRegistry.register
class Document(base.DeckhandPersistentObject, base.DeckhandObject):

    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'blob': ovo_fields.ObjectField('DocumentPayload', nullable=False),
        'name': ovo_fields.StringField(nullable=True),
        'revision_index': ovo_fields.NonNegativeIntegerField(nullable=False),
        'status': fields.DocumentField(nullable=False)
    }

    def __init__(self, **kwargs):
        super(Document, self).__init__(**kwargs)

    @property
    def name(self):
        return self.name

    @property
    def revision(self):
        return self.revision_index

    @property
    def status(self):
        return self.status
