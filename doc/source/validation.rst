..
  Copyright 2017 AT&T Intellectual Property.
  All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License"); you may
  not use this file except in compliance with the License. You may obtain
  a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
  License for the specific language governing permissions and limitations
  under the License.

.. _validation:

Document Validation
===================

Validations
-----------

The validation system provides a unified approach to complex validations that
require coordination of multiple documents and business logic that resides in
consumer services.

Services can report success or failure of named validations for a given
revision. Those validations can then be referenced by many ``ValidationPolicy``
control documents. The intended purpose use is to allow a simple mapping that
enables consuming services to be able to quickly check whether the
configuration in Deckhand is in a valid state for performing a specific
action.

Deckhand-Provided Validations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to allowing 3rd party services to report configurable validation
statuses, Deckhand provides a few internal validations which are made
available immediately upon document ingestion.

Here is a list of internal validations:

* ``deckhand-document-schema-validation`` - All concrete documents in the
  revision successfully pass their JSON schema validations. Will cause
  this to report an error.
* ``deckhand-policy-validation`` - All required policy documents are in-place,
  and existing documents conform to those policies.  E.g. if a 3rd party
  document specifies a ``layer`` that is not present in the layering policy,
  that will cause this validation to report an error.

Externally Provided Validations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As mentioned, other services can report whether named validations that have
been registered by those services as success or failure. ``DataSchema`` control
documents are used to register a new validation mapping that other services
can reference to verify whether a Deckhand bucket is in a valid configuration.
For more information, refer to the ``DataSchema`` section in
:ref:`document-types`.
