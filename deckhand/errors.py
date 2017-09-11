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


# TODO(fmontei): Remove this in a future commit.
class ApiError(Exception):
    pass


class InvalidFormat(ApiError):
    """The YAML file is incorrectly formatted and cannot be read."""


class DocumentExists(DeckhandException):
    msg_fmt = ("Document with schema %(schema)s and metadata.name "
               "%(name)s already exists in bucket %(bucket)s.")
    code = 409


class LayeringPolicyNotFound(DeckhandException):
    msg_fmt = ("LayeringPolicy with schema %(schema)s not found in the "
               "system.")
    code = 400


class LayeringPolicyMalformed(DeckhandException):
    msg_fmt = ("LayeringPolicy with schema %(schema)s is improperly formatted:"
               " %(document)s.")
    code = 400


class IndeterminateDocumentParent(DeckhandException):
    msg_fmt = ("Too many parent documents found for document %(document)s.")
    code = 400


class MissingDocumentParent(DeckhandException):
    msg_fmt = ("Missing parent document for document %(document)s.")
    code = 400


class MissingDocumentKey(DeckhandException):
    msg_fmt = ("Missing document key %(key)s from either parent or child. "
               "Parent: %(parent)s. Child: %(child)s.")


class UnsupportedActionMethod(DeckhandException):
    msg_fmt = ("Method in %(actions)s is invalid for document %(document)s.")
    code = 400


class DocumentNotFound(DeckhandException):
    msg_fmt = ("The requested document %(document)s was not found.")
    code = 404


class RevisionNotFound(DeckhandException):
    msg_fmt = "The requested revision %(revision)s was not found."
    code = 404


class RevisionTagNotFound(DeckhandException):
    msg_fmt = ("The requested tag %(tag)s for revision %(revision)s was not "
               "found.")
    code = 404


class RevisionTagBadFormat(DeckhandException):
    msg_fmt = ("The requested tag data %(data)s must either be null or "
               "dictionary.")
    code = 400


class BarbicanException(DeckhandException):

    def __init__(self, message, code):
        super(BarbicanException, self).__init__(message=message, code=code)
