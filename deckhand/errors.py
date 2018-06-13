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

import collections

import falcon
from oslo_log import log as logging
import six
import yaml

LOG = logging.getLogger(__name__)


def get_version_from_request(req):
    """Attempt to extract the API version string."""
    for part in req.path.split('/'):
        if '.' in part and part.startswith('v'):
            return part
    return 'N/A'


def _safe_yaml_dump(error_response):
    """Cast every instance of ``DocumentDict`` into a dictionary for
    compatibility with ``yaml.safe_dump``.

    This should only be called for error formatting.
    """
    is_dict_sublcass = (
        lambda v: type(v) is not dict and issubclass(v.__class__, dict)
    )

    def _to_dict(value, parent):
        if isinstance(value, (list, tuple, set)):
            for v in value:
                _to_dict(v, value)
        elif isinstance(value, collections.Mapping):
            for v in value.values():
                _to_dict(v, value)
        else:
            if isinstance(parent, (list, tuple, set)):
                parent[parent.index(value)] = (
                    dict(value) if is_dict_sublcass(value) else value)
            elif isinstance(parent, dict):
                for k, v in parent.items():
                    parent[k] = dict(v) if is_dict_sublcass(v) else v
    _to_dict(error_response, None)
    return yaml.safe_dump(error_response)


def format_error_resp(req,
                      resp,
                      status_code=falcon.HTTP_500,
                      message="",
                      reason=None,
                      error_type=None,
                      error_list=None,
                      info_list=None):
    """Generate a error message body and throw a Falcon exception to trigger
    an HTTP status.

    :param req: ``falcon`` request object.
    :param resp: ``falcon`` response object to update.
    :param status_code: ``falcon`` status_code constant.
    :param message: Optional error message to include in the body.
                    This should be the summary level of the error
                    message, encompassing an overall result. If
                    no other messages are passed in the error_list,
                    this message will be repeated in a generated
                    message for the output message_list.
    :param reason: Optional reason code to include in the body
    :param error_type: If specified, the error type will be used;
                       otherwise, this will be set to
                       'Unspecified Exception'.
    :param error_list: optional list of error dictionaries. Minimally,
                       the dictionary will contain the 'message' field,
                       but should also contain 'error': ``True``.
    :param info_list: optional list of info message dictionaries.
                      Minimally, the dictionary needs to contain a
                      'message' field, but should also have a
                      'error': ``False`` field.
    """

    error_type = error_type or 'Unspecified Exception'
    reason = reason or 'Unspecified'

    # Since we're handling errors here, if error list is None, set up a default
    # error item. If we have info items, add them to the message list as well.
    # In both cases, if the error flag is not set, set it appropriately.
    if not error_list:
        error_list = [{'message': message, 'error': True}]
    else:
        for error_item in error_list:
            if 'error' not in error_item:
                error_item['error'] = True

    if not info_list:
        info_list = []
    else:
        for info_item in info_list:
            if 'error' not in info_item:
                info_item['error'] = False

    message_list = error_list + info_list

    error_response = {
        'kind': 'Status',
        'apiVersion': get_version_from_request(req),
        'metadata': {},
        'status': 'Failure',
        'message': message,
        'reason': reason,
        'details': {
            'errorType': error_type,
            'errorCount': len(error_list),
            'messageList': message_list
        },
        'code': status_code,
        # TODO(fmontei): Make this class-specific later. For now, retry
        # is set to True only for internal server errors.
        'retry': True if status_code is falcon.HTTP_500 else False
    }

    resp.body = _safe_yaml_dump(error_response)
    resp.status = status_code


def default_exception_handler(ex, req, resp, params):
    """Catch-all exception handler for standardized output.

    If this is a standard falcon HTTPError, rethrow it for handling by
    ``default_exception_serializer`` below.
    """
    if isinstance(ex, falcon.HTTPError):
        # Allow the falcon HTTP errors to bubble up and get handled.
        raise ex
    elif isinstance(ex, DeckhandException):
        status_code = (getattr(falcon, 'HTTP_%d' % ex.code, falcon.HTTP_500)
                       if hasattr(ex, 'code') else falcon.HTTP_500)

        format_error_resp(
            req,
            resp,
            status_code=status_code,
            message=ex.message,
            error_type=ex.__class__.__name__,
            error_list=getattr(ex, 'error_list', None),
            reason=getattr(ex, 'reason', None)
        )
    else:
        # Take care of the uncaught stuff.
        format_error_resp(
            req,
            resp,
            error_type=ex.__class__.__name__,
            message="Unhandled Exception raised: %s" % six.text_type(ex)
        )


def default_exception_serializer(req, resp, exception):
    """Serializes instances of :class:`falcon.HTTPError` into YAML format and
    formats the error body so it adheres to the UCP error formatting standard.
    """
    format_error_resp(
        req,
        resp,
        status_code=exception.status,
        # TODO(fmontei): Provide an overall error message instead.
        message=exception.description,
        error_type=exception.__class__.__name__,
        error_list=getattr(exception, 'error_list', None),
        reason=getattr(exception, 'reason', None)
    )


class DeckhandException(Exception):
    """Base Deckhand Exception
    To correctly use this class, inherit from it and define
    a 'msg_fmt' property. That msg_fmt will get printf'd
    with the keyword arguments provided to the constructor.
    """
    msg_fmt = "An unknown exception occurred."

    def __init__(self, message=None, code=500, **kwargs):
        kwargs.setdefault('code', code)

        if not message:
            try:
                message = self.msg_fmt % kwargs
            except Exception:
                message = self.msg_fmt

        self.message = message
        self.reason = kwargs.pop('reason', None)

        error_list = kwargs.pop('error_list', [])
        self.error_list = []

        for error in error_list:
            if isinstance(error, str):
                error = {'message': error, 'error': True}
            else:
                error = error.format_message()
            self.error_list.append(error)

        super(DeckhandException, self).__init__(message)

    def format_message(self):
        return self.args[0]


class InvalidDocumentFormat(DeckhandException):
    """Schema validations failed for the provided document(s).

    **Troubleshoot:**
    """
    msg_fmt = ("The provided documents failed schema validation.")
    code = 400


class InvalidDocumentLayer(DeckhandException):
    """The document layer is invalid.

    **Troubleshoot:**

    * Check that the document layer is contained in the layerOrder in the
      registered LayeringPolicy in the system.
    """
    msg_fmt = ("Invalid layer '%(document_layer)s' for document "
               "[%(document_schema)s] %(document_name)s was not found in "
               "layerOrder: %(layer_order)s for provided LayeringPolicy: "
               "%(layering_policy_name)s.")
    code = 400


class InvalidDocumentParent(DeckhandException):
    """The document parent is invalid.

    **Troubleshoot:**

    * Check that the document `schema` and parent `schema` match.
    * Check that the document layer is lower-order than the parent layer.
    """
    msg_fmt = ("The document parent [%(parent_schema)s] %(parent_name)s is "
               "invalid for document [%(document_schema)s] %(document_name)s. "
               "Reason: %(reason)s")
    code = 400


class IndeterminateDocumentParent(DeckhandException):
    """More than one parent document was found for a document.

    **Troubleshoot:**
    """
    msg_fmt = ("Too many parent documents found for document [%(schema)s, "
               "%(layer)s] %(name)s. Found: %(found)s. Expected: 1.")
    code = 400


class SubstitutionDependencyCycle(DeckhandException):
    """An illegal substitution depdencency cycle was detected.

    **Troubleshoot:**

    * Check that there is no two-way substitution dependency between documents.
    """
    msg_fmt = ('Cannot determine substitution order as a dependency '
               'cycle exists for the following documents: %(cycle)s.')
    code = 400


class MissingDocumentKey(DeckhandException):
    """Either the parent or child document data is missing the action path
    used for layering.

    **Troubleshoot:**

    * Check that the action path exists in the data section for both child
      and parent documents being layered together.
    * Note that previous delete layering actions can affect future layering
      actions by removing a path needed by a future layering action.
    * Note that substitutions that substitute in lists or objects into the
      rendered data for a document can also complicate debugging this issue.
    """
    msg_fmt = ("Missing action path in %(action)s needed for layering from "
               "either the data section of the parent [%(parent_schema)s, "
               "%(parent_layer)s] %(parent_name)s or child [%(child_schema)s, "
               "%(child_layer)s] %(child_name)s "
               "document.")
    code = 400


class MissingDocumentPattern(DeckhandException):
    """'Pattern' is not None and data[jsonpath] doesn't exist.

    **Troubleshoot:**

    * Check that the destination document's data section contains the
      pattern specified under `substitutions.dest.pattern` in its data
      section at `substitutions.dest.path`.
    """
    msg_fmt = ("The destination document's `data` section is missing the "
               "pattern %(pattern)s specified under "
               "`substitutions.dest.pattern` at path %(jsonpath)s, specified "
               "under `substitutions.dest.path`.")
    code = 400


class InvalidDocumentReplacement(DeckhandException):
    """The document replacement is invalid.

    **Troubleshoot:**

    * Check that the replacement document has the same ``schema`` and
      ``metadata.name`` as the document it replaces.
    * Check that the document with ``replacement: true`` has a parent.
    * Check that the document replacement isn't being replaced by another
      document. Only one level of replacement is permitted.
    """
    msg_fmt = ("Replacement document [%(schema)s, %(layer)s] %(name)s is "
               "invalid. Reason: %(reason)s")
    code = 400


class UnsupportedActionMethod(DeckhandException):
    """The action is not in the list of supported methods.

    **Troubleshoot:**
    """
    msg_fmt = ("Method in %(actions)s is invalid for document %(document)s.")
    code = 400


class RevisionTagBadFormat(DeckhandException):
    """The tag data is neither None nor dictionary.

    **Troubleshoot:**
    """
    msg_fmt = ("The requested tag data %(data)s must either be null or "
               "dictionary.")
    code = 400


class SubstitutionSourceDataNotFound(DeckhandException):
    """Required substitution source secret was not found in the substitution
    source document at the path ``metadata.substitutions.[*].src.path`` in the
    destination document.

    **Troubleshoot:**

    * Ensure that the missing source secret exists at the ``src.path``
      specified under the given substitution in the destination document and
      that the ``src.path`` itself exists in the source document.
    """
    msg_fmt = (
        "Required substitution source secret was not found at path "
        "%(src_path)s in source document [%(src_schema)s, %(src_layer)s] "
        "%(src_name)s which is referenced by destination document "
        "[%(dest_schema)s, %(dest_layer)s] %(dest_name)s under its "
        "`metadata.substitutions`.")
    code = 400


class EncryptionSourceNotFound(DeckhandException):
    """Required encryption source reference was not found.

    **Troubleshoot:**

    * Ensure that the secret reference exists among the encryption sources.
    """
    msg_fmt = (
        "Required encryption source reference could not be resolved into a "
        "secret because it was not found among encryption sources. Ref: "
        "%(secret_ref)s. Referenced by: [%(schema)s, %(layer)s] %(name)s.")
    code = 400  # Indicates bad data was passed in, causing a lookup to fail.


class DocumentNotFound(DeckhandException):
    """The requested document could not be found.

    **Troubleshoot:**
    """
    msg_fmt = ("The requested document using filters: %(filters)s was not "
               "found.")
    code = 404


class RevisionNotFound(DeckhandException):
    """The revision cannot be found or doesn't exist.

    **Troubleshoot:**
    """
    msg_fmt = "The requested revision=%(revision_id)s was not found."
    code = 404


class RevisionTagNotFound(DeckhandException):
    """The tag for the revision id was not found.

    **Troubleshoot:**
    """
    msg_fmt = ("The requested tag '%(tag)s' for revision %(revision)s was "
               "not found.")
    code = 404


class ValidationNotFound(DeckhandException):
    """The requested validation was not found.

    **Troubleshoot:**
    """
    msg_fmt = ("The requested validation entry %(entry_id)s was not found "
               "for validation name %(validation_name)s and revision ID "
               "%(revision_id)s.")
    code = 404


class DuplicateDocumentExists(DeckhandException):
    """A document attempted to be put into a bucket where another document with
    the same schema and metadata.name already exist.

    **Troubleshoot:**
    """
    msg_fmt = ("Document [%(schema)s, %(layer)s] %(name)s already exists in "
               "bucket: %(bucket)s.")
    code = 409


class SingletonDocumentConflict(DeckhandException):
    """A singleton document already exist within the system.

    **Troubleshoot:**
    """

    msg_fmt = ("A singleton document [%(schema)s, %(layer)s] %(name)s already "
               "exists in the system. The new document(s) %(conflict)s cannot "
               "be created. To create a document with a new name, delete the "
               "current one first.")
    code = 409


class LayeringPolicyNotFound(DeckhandException):
    """Required LayeringPolicy was not found for layering.

    **Troubleshoot:**
    """
    msg_fmt = ("Required LayeringPolicy was not found for layering.")
    code = 409


class SubstitutionSourceNotFound(DeckhandException):
    """Required substitution source document was not found.

    **Troubleshoot:**

    * Ensure that the missing source document being referenced exists in
      the system or was passed to the layering module.
    """
    msg_fmt = (
        "Required substitution source document [%(src_schema)s] %(src_name)s "
        "was not found, yet is referenced by [%(document_schema)s] "
        "%(document_name)s.")
    code = 409


class PolicyNotAuthorized(DeckhandException):
    """The policy action is not found in the list of registered rules.

    **Troubleshoot:**
    """
    msg_fmt = "Policy doesn't allow %(action)s to be performed."
    code = 403


class BarbicanClientException(DeckhandException):
    """A client-side 4xx error occurred with Barbican.

    **Troubleshoot:**

    * Ensure that Deckhand can authenticate against Keystone.
    * Ensure that Deckhand's Barbican configuration options are correct.
    * Ensure that Deckhand and Barbican are contained in the Keystone service
      catalog.
    """
    msg_fmt = 'Barbican raised a client error. Details: %(details)s'
    code = 400  # Needs to be overridden.


class BarbicanServerException(DeckhandException):
    """A server-side 5xx error occurred with Barbican."""
    msg_fmt = ('Barbican raised a server error. Details: %(details)s')
    code = 500


class UnknownSubstitutionError(DeckhandException):
    """An unknown error occurred during substitution.

    **Troubleshoot:**
    """
    code = 500

    def __init__(self, *args, **kwargs):
        super(UnknownSubstitutionError, self).__init__(*args, **kwargs)
        dest_args = ('schema', 'layer', 'name')
        msg_format = ('An unknown exception occurred while trying to perform '
                      'substitution using source document [%(src_schema)s, '
                      '%(src_layer)s] %(src_name)s')
        if all(x in args for x in dest_args):
            msg_format += (' contained in document [%(schema)s, %(layer)s]'
                           ' %(name)s')
        msg_format += '. Details: %(detail)s'
        self.msg_fmt = msg_format
