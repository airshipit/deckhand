# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

import falcon
import six

from oslo_log import log as logging
from oslo_utils import excutils

from deckhand.common import utils
from deckhand.control import base as api_base
from deckhand.engine.revision_diff import revision_diff
from deckhand import errors
from deckhand import policy

LOG = logging.getLogger(__name__)


class RevisionDeepDiffingResource(api_base.BaseResource):
    """API resource for realizing revision deepdiffing."""

    @policy.authorize('deckhand:show_revision_deepdiff')
    def on_get(self, req, resp, revision_id, comparison_revision_id):
        try:
            revision_id = int(revision_id)
        except ValueError:
            raise errors.InvalidInputException(input_var=six.text_type(
                revision_id))
        try:
            comparison_revision_id = int(comparison_revision_id)
        except ValueError:
            raise errors.InvalidInputException(
                input_var=six.text_type(comparison_revision_id))

        try:
            resp_body = revision_diff(
                revision_id, comparison_revision_id, deepdiff=True)
        except errors.RevisionNotFound as e:
            with excutils.save_and_reraise_exception():
                message = (e.format_message())
                LOG.exception(message)

        resp.status = falcon.HTTP_200
        resp.text = utils.safe_yaml_dump(resp_body)
