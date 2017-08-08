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
    cfg.StrOpt(
        'api_endpoint',
        sample_default='http://barbican.example.org:9311/',
        help='URL override for the Barbican API endpoint.'),
]


def register_opts(conf):
    conf.register_group(barbican_group)
    conf.register_opts(barbican_opts, group=barbican_group)
    ks_loading.register_auth_conf_options(conf, group=barbican_group.name)
    ks_loading.register_session_conf_options(conf, group=barbican_group.name)


def list_opts():
    opts = {barbican_group: barbican_opts +
                            ks_loading.get_session_conf_options() +
                            ks_loading.get_auth_common_conf_options() +
                            ks_loading.get_auth_plugin_conf_options(
                                'v3password')}
    return opts


def parse_args(args=None, usage=None, default_config_files=None):
    CONF(args=args,
         project='deckhand',
         usage=usage,
         default_config_files=default_config_files)


def parse_cache_args(args=None):
    # Look for Deckhand config files in the following directories::
    #
    #  ~/.${project}/
    #  ~/
    #  /etc/${project}/
    #  /etc/
    #  ${SNAP}/etc/${project}
    #  ${SNAP_COMMON}/etc/${project}
    config_files = cfg.find_config_files(project='deckhand')
    parse_args(args=args, default_config_files=config_files)


register_opts(CONF)
