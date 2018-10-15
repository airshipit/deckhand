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

from keystoneauth1 import loading as ks_loading
from oslo_config import cfg

CONF = cfg.CONF


barbican_group = cfg.OptGroup(
    name='barbican',
    title='Barbican Options',
    help="Barbican options for allowing Deckhand to communicate with "
         "Barbican.")


barbican_opts = [
    # TODO(felipemonteiro): Drop this option once Keystone endpoint lookup is
    # implemented.
    cfg.StrOpt(
        'api_endpoint',
        sample_default='http://barbican.example.org:9311/',
        help='URL override for the Barbican API endpoint.'),
    cfg.IntOpt(
        'max_workers', default=10,
        help='Maximum number of threads used to call secret storage service '
             'concurrently.'),
    # TODO(felipemonteiro): This is better off being removed because the same
    # effect can be achieved through per-test gabbi fixtures that clean up
    # the cache between tests.
    cfg.BoolOpt('enable_cache', default=True,
                help="Whether to enable Barbican secret caching. Useful "
                     "for testing to avoid cross-test caching conflicts."),
    cfg.StrOpt(
        'cache_timeout', default=3600,
        help="How long (in seconds) Barbican secret reference/payload lookup "
             "results should remain cached in memory.")
]


engine_group = cfg.OptGroup(
    name='engine',
    title='Engine Options',
    help="Engine options for allowing behavior specific to Deckhand's engine "
         "to be configured.")


engine_opts = [
    # TODO(felipemonteiro): This is better off being removed because the same
    # effect can be achieved through per-test gabbi fixtures that clean up
    # the cache between tests.
    cfg.BoolOpt('enable_cache', default=True,
                help="Whether to enable the document rendering caching. Useful"
                     " for testing to avoid cross-test caching conflicts."),
    cfg.IntOpt('cache_timeout', default=3600,
               help="How long (in seconds) document rendering results should "
                    "remain cached in memory."),
]


jsonpath_group = cfg.OptGroup(
    name='jsonpath',
    title='JSONPath Options',
    help="JSONPath options for allowing JSONPath logic to be configured.")


jsonpath_opts = [
    cfg.IntOpt('cache_timeout', default=3600,
               help="How long (in seconds) JSONPath lookup results should "
                    "remain cached in memory.")
]


default_opts = [
    cfg.BoolOpt('profiler', default=False,
                help="Enables profiling of API requests. Do NOT use in "
                     "production."),
    cfg.BoolOpt('development_mode', default=False,
                help="Enables development mode, which disables Keystone "
                     "authentication. Do NOT use in production.")
]


def register_opts(conf):
    conf.register_group(barbican_group)
    conf.register_opts(barbican_opts, group=barbican_group)
    conf.register_opts(engine_opts, group=engine_group)
    conf.register_opts(jsonpath_opts, group=jsonpath_group)
    conf.register_opts(default_opts)
    ks_loading.register_auth_conf_options(conf, group='keystone_authtoken')
    ks_loading.register_auth_conf_options(conf, group=barbican_group.name)
    ks_loading.register_session_conf_options(conf, group=barbican_group.name)


def list_opts():
    opts = {
        None: default_opts,
        'keystone_authtoken': (
            ks_loading.get_session_conf_options() +
            ks_loading.get_auth_common_conf_options() +
            ks_loading.get_auth_plugin_conf_options('password') +
            ks_loading.get_auth_plugin_conf_options('v3password')
        ),
        engine_group: engine_opts,
        barbican_group: (
            barbican_opts +
            ks_loading.get_session_conf_options() +
            ks_loading.get_auth_common_conf_options() +
            ks_loading.get_auth_plugin_conf_options('v3password')
        ),
        jsonpath_group: jsonpath_opts
    }
    return opts


register_opts(CONF)
