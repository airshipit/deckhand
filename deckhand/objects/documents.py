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
# Models for deckhand
#

from oslo_log import log as logging
import oslo_versionedobjects.fields as ovo_fields

from deckhand.db import api_models
from deckhand import objects
from deckhand.objects import base
from deckhand.objects import fields as deckhand_fields

LOG = logging.getLogger(__name__)


class DocumentPayload(base.DeckhandPayloadBase):

    SCHEMA = {
        #'instance_key': ('document', 'instance_key'),
        'metadata': ('document', 'metadata'),
        'data': ('document', 'data')
    }

    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        #'instance_key': ovo_fields.StringField(nullable=False),
        'metadata': ovo_fields.DictOfStringsField(nullable=False),
        'data': ovo_fields.DictOfStringsField(nullable=False)
    }

    def __init__(self, document):
        super(DocumentPayload, self).__init__()
        LOG.debug(document)
        self.populate_schema(document=document)


@base.DeckhandObjectRegistry.register
class Document(base.DeckhandPersistentObject, base.DeckhandObject):

    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'id': ovo_fields.IntegerField(nullable=False, read_only=True),
        'blob': ovo_fields.ObjectField('DocumentPayload', nullable=False),
        'revision_index': ovo_fields.NonNegativeIntegerField(nullable=False),
        'status': ovo_fields.StringField(nullable=False)
    }

    def __init__(self, *args, **kwargs):
        super(Document, self).__init__(*args, **kwargs)
        # Set up defaults.
        self.obj_reset_changes()

    def create(self, document):
        #updates = self.obj_get_changes()
        LOG.debug(document)
        self.blob = DocumentPayload(document)
        #api_models.Document()
