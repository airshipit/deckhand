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

import functools
import six

import falcon
from oslo_config import cfg
from oslo_log import log as logging
from oslo_policy import policy

from deckhand import errors
from deckhand import policies

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
_ENFORCER = None


def reset():
    global _ENFORCER
    if _ENFORCER:
        _ENFORCER.clear()
        _ENFORCER = None


def init(policy_file=None, rules=None, default_rule=None, use_conf=True):
    """Init an Enforcer class.

    :param policy_file: Custom policy file to use, if none is specified,
        ``CONF.policy_file`` will be used.
    :param rules: Default dictionary / Rules to use. It will be
        considered just in the first instantiation.
    :param default_rule: Default rule to use; ``CONF.default_rule`` will
        be used if none is specified.
    :param use_conf: Whether to load rules from config file.
    """

    global _ENFORCER

    if not _ENFORCER:
        _ENFORCER = policy.Enforcer(CONF,
                                    policy_file=policy_file,
                                    rules=rules,
                                    default_rule=default_rule,
                                    use_conf=use_conf)
        register_rules(_ENFORCER)


def _do_enforce_rbac(action, context, do_raise=True):
    init()

    credentials = context.to_policy_values()
    target = {'project_id': context.project_id,
              'user_id': context.user_id}
    exc = errors.PolicyNotAuthorized

    try:
        # `oslo.policy` supports both enforce and authorize. authorize is
        # stricter because it'll raise an exception if the policy action is
        # not found in the list of registered rules. This means that attempting
        # to enforce anything not found in ``deckhand.policies`` will error out
        # with a 'Policy not registered' message.
        return _ENFORCER.authorize(
            action, target, context.to_dict(), do_raise=do_raise,
            exc=exc, action=action)
    except policy.PolicyNotRegistered as e:
        LOG.exception('Policy not registered.')
        raise falcon.HTTPForbidden(description=six.text_type(e))
    except Exception as e:
        LOG.debug(
            'Policy check for %(action)s failed with credentials '
            '%(credentials)s',
            {'action': action, 'credentials': credentials})
        raise falcon.HTTPForbidden(description=six.text_type(e))


def authorize(action):
    """Verifies whether a policy action can be performed given the credentials
    found in the falcon request context.

    :param action: The policy action to enforce.
    :returns: ``True`` if policy enforcement succeeded, else ``False``.
    :raises: falcon.HTTPForbidden if policy enforcement failed or if the policy
        action isn't registered under ``deckhand.policies``.
    """
    def decorator(func):
        @functools.wraps(func)
        def handler(*args, **kwargs):
            # args[1] is always the falcon Request object.
            context = args[1].context
            _do_enforce_rbac(action, context)
            return func(*args, **kwargs)
        return handler

    return decorator


def conditional_authorize(action, context, do_raise=True):
    """Conditionally authorize a policy action.

    :param action: The policy action to enforce.
    :param context: The falcon request context object.
    :param do_raise: Whether to raise the exception if policy enforcement
        fails. ``True`` by default.
    :raises: falcon.HTTPForbidden if policy enforcement failed or if the policy
        action isn't registered under ``deckhand.policies``.

    Example::

        # If any requested documents' metadata.storagePolicy == 'cleartext'.
        if cleartext_documents:
            policy.conditional_authorize('deckhand:create_cleartext_documents',
                                         req.context)
    """
    return _do_enforce_rbac(action, context, do_raise=do_raise)


def register_rules(enforcer):
    enforcer.register_defaults(policies.list_rules())
