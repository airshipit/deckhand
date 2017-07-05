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

from oslo_config import cfg

barbican_group = cfg.OptGroup(
    name='barbican',
    title='Barbican Options',
    help="""
Barbican options for allowing Deckhand to communicate with Barbican.
""")

barbican_opts = []

logging_group = cfg.OptGroup(
    name='logging',
    title='Logging Options',
    help='Logging options for Deckhand.')

logging_opts = [
    cfg.StrOpt('global_logger_name',
                default='deckhand',
                help='Logger name for the top-level logger.')
]


def register_opts(conf):
    conf.register_group(barbican_group)
    conf.register_opts(barbican_opts, group=barbican_group)
    conf.register_group(logging_group)
    conf.register_opts(logging_opts, group=logging_group)


def list_opts():
    return {barbican_group: barbican_opts,
            logging_group: logging_opts}
