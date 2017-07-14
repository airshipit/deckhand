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


class DeckhandException(Exception):
    """Base Deckhand Exception
    To correctly use this class, inherit from it and define
    a 'msg_fmt' property. That msg_fmt will get printf'd
    with the keyword arguments provided to the constructor.
    """
    msg_fmt = "An unknown exception occurred."
    code = 500

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            try:
                message = self.msg_fmt % kwargs

            except Exception:
                message = self.msg_fmt

        self.message = message
        super(DeckhandException, self).__init__(message)

    def format_message(self):
        return self.args[0]


class InvalidDocumentFormat(DeckhandException):
    msg_fmt = ("The provided YAML failed schema validation. Details: "
               "%(detail)s. Schema: %(schema)s.")
    alt_msg_fmt = ("The provided %(document_type)s YAML failed schema "
                   "validation. Details: %(detail)s. Schema: %(schema)s.")

    def __init__(self, document_type=None, **kwargs):
        if document_type:
            self.msg_fmt = self.alt_msg_fmt
            kwargs.update({'document_type': document_type})
        super(InvalidDocumentFormat, self).__init__(**kwargs)


class UnknownDocumentFormat(DeckhandException):
    msg_fmt = ("Could not determine the validation schema to validate the "
                "document type: %(document_type)s.")
    code = 400


class RevisionNotFound(DeckhandException):
    msg_fmt = ("The requested revision %(revision)s was not found.")
    code = 403
