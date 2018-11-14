Deckhand Style Commandments
===========================

- Step 1: Read the OpenStack Style Commandments
  https://docs.openstack.org/hacking/latest/
- Step 2: Read on

Deckhand Specific Commandments
------------------------------

- [D316] Change assertTrue(isinstance(A, B)) by optimal assert like
  assertIsInstance(A, B).
- [D317] Change assertEqual(type(A), B) by optimal assert like
  assertIsInstance(A, B).
- [D320] Setting CONF.* attributes directly in tests is forbidden.
- [D322] Method's default argument shouldn't be mutable.
- [D324] Ensure that jsonutils.%(fun)s must be used instead of json.%(fun)s
- [D325] str() and unicode() cannot be used on an exception. Remove use or use six.text_type()
- [D334] Change assertTrue/False(A in/not in B, message) to the more specific
  assertIn/NotIn(A, B, message)
- [D335] Check for usage of deprecated assertRaisesRegexp
- [D336] Must use a dict comprehension instead of a dict constructor with a sequence of key-value pairs.
- [D338] Change assertEqual(A in B, True), assertEqual(True, A in B),
  assertEqual(A in B, False) or assertEqual(False, A in B) to the more specific
  assertIn/NotIn(A, B)
- [D339] Check common raise_feature_not_supported() is used for v2.1 HTTPNotImplemented response.
- [D344] Python 3: do not use dict.iteritems.
- [D345] Python 3: do not use dict.iterkeys.
- [D346] Python 3: do not use dict.itervalues.
- [D350] Policy registration should be in the central location ``deckhand/policies/``.
- [D352] LOG.warn is deprecated. Enforce use of LOG.warning.
- [D355] Enforce use of assertTrue/assertFalse
- [D356] Enforce use of assertIs/assertIsNot
- [D357] Use oslo_utils.uuidutils or uuidsentinel(in case of test cases) to
  generate UUID instead of uuid4().
- [D358] Return must always be followed by a space when returning a value.

Creating Unit Tests
-------------------
For every new feature, unit tests should be created that both test and
(implicitly) document the usage of said feature. If submitting a patch for a
bug that had no unit test, a new passing unit test should be added. If a
submitted bug fix does have a unit test, be sure to add a new one that fails
without the patch and passes with the patch.

Running Tests
-------------
The testing system is based on a combination of tox and testr. The canonical
approach to running tests is to simply run the command ``tox``. This will
create virtual environments, populate them with dependencies and run all of
the tests that OpenStack CI systems run. Behind the scenes, tox is running
``testr run --parallel``, but is set up such that you can supply any additional
testr arguments that are needed to tox. For example, you can run:
``tox -- --analyze-isolation`` to cause tox to tell testr to add
--analyze-isolation to its argument list.

Functional testing leverages gabbi and requires docker as a prerequisite to be
run. Functional tests can be executing by running the command
``tox -e functional``.

Building Docs
-------------
Normal Sphinx docs can be built via the setuptools ``build_sphinx`` command. To
do this via ``tox``, simply run ``tox -e docs``,
which will cause a virtualenv with all of the needed dependencies to be
created and then inside of the virtualenv, the docs will be created and
put into doc/build/html.
