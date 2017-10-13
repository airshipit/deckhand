..
  Copyright 2017 AT&T Intellectual Property.  All other rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.


Rest API Policy Enforcement
===========================
Policy enforcement in Deckhand leverages the ``oslo.policy`` library like
all OpenStack projects. The implementation is located in ``deckhand.policy``.
Two types of policy authorization exist in Deckhand:

    1) Decorator-level authorization used for wrapping around ``falcon``
       "on_{HTTP_VERB}" methods. In this case, if policy authorization fails
       a 403 Forbidden is always raised.
    2) Conditional authorization, which means that the policy is only enforced
       if a certain set of conditions are true.

Deckhand, for example, will only conditionally enforce listing encrypted
documents if a document's ``metadata.storagePolicy`` is "encrypted".

Policy Implementation
---------------------

Deckhand uses ``authorize`` from ``oslo.policy`` as the latter supports both
``enforce`` and ``authorize``. ``authorize`` is stricter because it'll raise an
exception if the policy action is not registered under ``deckhand.policies``
(which enumerates all the legal policy actions and their default rules). This
means that attempting to enforce anything not found in ``deckhand.policies``
will error out with a 'Policy not registered' message.

.. automodule:: deckhand.policy
   :members:

Sample Policy File
==================
The following is a sample Deckhand policy file for adaptation and use. It is
auto-generated from Deckhand when this documentation is built, so
if you are having issues with an option, please compare your version of
Deckhand with the version of this documentation.

The sample configuration can also be viewed in `file form <_static/deckhand.policy.yaml.sample>`_.

.. literalinclude:: _static/deckhand.policy.yaml.sample
