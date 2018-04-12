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
    help="""
Barbican options for allowing Deckhand to communicate with Barbican.
""")

barbican_opts = [
    # TODO(fmontei): Drop these options and related group once Keystone
    # endpoint lookup is used instead.
    cfg.StrOpt(
        'api_endpoint',
        sample_default='http://barbican.example.org:9311/',
        help='URL override for the Barbican API endpoint.'),
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
    conf.register_opts(default_opts)
    ks_loading.register_auth_conf_options(conf, group=barbican_group.name)
    ks_loading.register_session_conf_options(conf, group=barbican_group.name)


def list_opts():
    opts = {None: default_opts,
            barbican_group: barbican_opts +
                            ks_loading.get_session_conf_options() +
                            ks_loading.get_auth_common_conf_options() +
                            ks_loading.get_auth_plugin_conf_options(
                                'v3password')}
    return opts


register_opts(CONF)
