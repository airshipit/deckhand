Reviewing Deckhand Code
=======================
To start read the `OpenStack Common Review Checklist
<https://docs.openstack.org/infra/manual/developers.html#peer-review>`_


Unit Tests
----------
For any change that adds new functionality to either common functionality or
fixes a bug unit tests are required. This is to ensure we don't introduce
future regressions and to test conditions which we may not hit in the gate
runs.


Functional Tests
----------------
For any change that adds major new functionality functional tests are required.
This is to ensure that the Deckhand API follows the contract it promises.
In addition, functional tests are run against the Deckhand container, which
uses an image built from the latest source code to validate the integrity
of the image.


Deprecated Code
---------------
Deprecated code should go through a deprecation cycle -- long enough for other
Airship projects to modify their code base to reference new code. Features,
APIs or configuration options are marked deprecated in the code. Appropriate
warnings will be sent to the end user, operator or library user.


When to approve
---------------
* Every patch needs two +2s before being approved.
* Its OK to hold off on an approval until a subject matter expert reviews it.
* If a patch has already been approved but requires a trivial rebase to merge,
  you do not have to wait for a second +2, since the patch has already had
  two +2s.
