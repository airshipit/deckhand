# Copyright 2012 Hewlett-Packard Development Company, L.P.
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

"""Fixtures for Deckhand tests."""
from __future__ import absolute_import

import os
import yaml

import fixtures
from oslo_config import cfg
from oslo_policy import opts as policy_opts
from oslo_policy import policy as oslo_policy

from deckhand import policies
import deckhand.policy
from deckhand.tests.unit import fake_policy

CONF = cfg.CONF


class ConfPatcher(fixtures.Fixture):
    """Fixture to patch and restore global CONF.

    This also resets overrides for everything that is patched during
    it's teardown.

    """

    def __init__(self, **kwargs):
        """Constructor

        :params group: if specified all config options apply to that group.

        :params **kwargs: the rest of the kwargs are processed as a
        set of key/value pairs to be set as configuration override.

        """
        super(ConfPatcher, self).__init__()
        self.group = kwargs.pop('group', None)
        self.args = kwargs

    def setUp(self):
        super(ConfPatcher, self).setUp()
        for k, v in self.args.items():
            self.addCleanup(CONF.clear_override, k, self.group)
            CONF.set_override(k, v, self.group)


class RealPolicyFixture(fixtures.Fixture):
    """Load the live policy for tests.

    A base policy fixture that starts with the assumption that you'd
    like to load and enforce the shipped default policy in tests.

    """

    def setUp(self):
        super(RealPolicyFixture, self).setUp()
        self.policy_dir = self.useFixture(fixtures.TempDir())
        self.policy_file = os.path.join(self.policy_dir.path,
                                        'policy.yaml')
        # Load the fake_policy data and add the missing default rules.
        policy_rules = yaml.safe_load(fake_policy.policy_data)
        self.add_missing_default_rules(policy_rules)
        with open(self.policy_file, 'w') as f:
            yaml.safe_dump(policy_rules, f)

        policy_opts.set_defaults(CONF)
        CONF.set_override('policy_dirs', [], group='oslo_policy')
        CONF.set_override('policy_file', self.policy_file, group='oslo_policy')

        deckhand.policy.reset()
        deckhand.policy.init()
        self.addCleanup(deckhand.policy.reset)

    def add_missing_default_rules(self, rules):
        """Adds default rules and their values to the given rules dict.

        The given rulen dict may have an incomplete set of policy rules.
        This method will add the default policy rules and their values to
        the dict. It will not override the existing rules.
        """
        for rule in policies.list_rules():
            if rule.name not in rules:
                rules[rule.name] = rule.check_str

    def set_rules(self, rules, overwrite=True):
        if isinstance(rules, dict):
            rules = oslo_policy.Rules.from_dict(rules)

        policy = deckhand.policy._ENFORCER
        policy.set_rules(rules, overwrite=overwrite)
