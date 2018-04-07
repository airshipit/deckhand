Functional Tests
================

Deckhand uses `gabbi`_ to drive its functional tests. The entry point for
these tests is ``functional-tests.sh`` under ``tools`` directory.

Directory Test Layout
---------------------

Tests are contained in intuitively named subdirectories nested under
``deckhand/tests/functional/gabbits``. For example, layering tests are
contained under the ``layering`` subdirectory. This pattern should be strictly
followed.

Because `gabbi`_ does not support loading tests from subdirectories, logic
is included in ``test_gabbi.py`` to:

#. Create a temporary directory.
#. Create a symlink between all the test files in the nested subdirectories
   and the temporary directory.

However, the test directory can still be modified:

* New subdirectories under ``gabbits`` can be added.
* New tests under any of those subdirectories can be added.
* New resource files under ``gabits/resources`` can be added. This directory
  name should never be renamed.
* All other subdirectories, test files, and resources may be renamed.

.. _gabbi: https://gabbi.readthedocs.io/en/latest/gabbi.html
