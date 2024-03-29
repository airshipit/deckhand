# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os

import falcon
from oslo_config import cfg
from oslo_log import log
from werkzeug.middleware.profiler import ProfilerMiddleware

from deckhand.control import base
from deckhand.control import buckets
from deckhand.control import health
from deckhand.control import middleware
from deckhand.control import revision_deepdiffing
from deckhand.control import revision_diffing
from deckhand.control import revision_documents
from deckhand.control import revision_tags
from deckhand.control import revisions
from deckhand.control import rollback
from deckhand.control import validations
from deckhand.control import versions
from deckhand import errors

CONF = cfg.CONF
LOG = log.getLogger(__name__)


def configure_app(app, version=''):

    v1_0_routes = [
        ('buckets/{bucket_name}/documents', buckets.BucketsResource()),
        ('health', health.HealthResource()),
        ('revisions', revisions.RevisionsResource()),
        ('revisions/{revision_id}', revisions.RevisionsResource()),
        ('revisions/{revision_id}/deepdiff/{comparison_revision_id}',
            revision_deepdiffing.RevisionDeepDiffingResource()),
        ('revisions/{revision_id}/diff/{comparison_revision_id}',
            revision_diffing.RevisionDiffingResource()),
        ('revisions/{revision_id}/documents',
            revision_documents.RevisionDocumentsResource()),
        ('revisions/{revision_id}/rendered-documents',
            revision_documents.RenderedDocumentsResource()),
        ('revisions/{revision_id}/tags', revision_tags.RevisionTagsResource()),
        ('revisions/{revision_id}/tags/{tag}',
            revision_tags.RevisionTagsResource()),
        ('revisions/{revision_id}/validations',
            validations.ValidationsResource()),
        ('revisions/{revision_id}/validations/detail',
            validations.ValidationsDetailsResource()),
        ('revisions/{revision_id}/validations/{validation_name}',
            validations.ValidationsResource()),
        ('revisions/{revision_id}/validations/{validation_name}'
         '/entries/{entry_id}',
            validations.ValidationsResource()),
        # min=0 is used as revision rollback supports 0.
        ('rollback/{revision_id:int(min=0)}', rollback.RollbackResource())
    ]

    for path, res in v1_0_routes:
        app.add_route(os.path.join('/api/%s' % version, path), res)
    app.add_route('/versions', versions.VersionsResource())

    # Error handlers (FILO handling).
    app.add_error_handler(Exception, errors.default_exception_handler)
    # Built-in error serializer.
    app.set_error_serializer(errors.default_exception_serializer)

    return app


def deckhand_app_factory(global_config, **local_config):
    # The order of the middleware is important because the `process_response`
    # method for `YAMLTranslator` should execute after that of any other
    # middleware to convert the response to YAML format.
    middleware_list = [middleware.YAMLTranslator(),
                       middleware.ContextMiddleware(),
                       middleware.LoggingMiddleware()]

    app = falcon.App(request_type=base.DeckhandRequest,
                     middleware=middleware_list)
    if CONF.profiler:
        LOG.warning("Profiler ENABLED. Expect significant "
                    "performance overhead.")
        profile_dir = "/tmp/profiles"  # nosec w/o profile data
        if not os.path.isdir(profile_dir):
            os.mkdir(profile_dir)
        LOG.debug("Profiler artifacts will be saved to %s.", profile_dir)
        return ProfilerMiddleware(
            configure_app(app, version='v1.0'),
            profile_dir=profile_dir)
    else:
        return configure_app(app, version='v1.0')
