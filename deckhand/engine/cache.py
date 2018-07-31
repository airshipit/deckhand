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

from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from oslo_log import log as logging

from deckhand.conf import config
from deckhand.engine import layering

CONF = config.CONF
LOG = logging.getLogger(__name__)

_CACHE_OPTS = {
    'cache.type': 'memory',
    'expire': CONF.engine.cache_timeout,
}
_CACHE = CacheManager(**parse_cache_config_options(_CACHE_OPTS))
_DOCUMENT_RENDERING_CACHE = _CACHE.get_cache('rendered_documents_cache')


def lookup_by_revision_id(revision_id, documents, **kwargs):
    """Look up rendered documents by ``revision_id``."""

    def do_render():
        """Perform document rendering for the revision."""
        document_layering = layering.DocumentLayering(documents, **kwargs)
        return document_layering.render()

    if CONF.engine.enable_cache:
        return _DOCUMENT_RENDERING_CACHE.get(key=revision_id,
                                             createfunc=do_render)
    else:
        return do_render()


def invalidate():
    _DOCUMENT_RENDERING_CACHE.clear()
