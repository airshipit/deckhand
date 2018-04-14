Integration Tests
=================

What
----

These tests validate integration scenarios between Deckhand, Keystone
and Barbican. These scenarios include validating Deckhand's secret
lifecycle management as well as substitution of encrypted secrets,
which are stored in Barbican and retrieved by Deckhand during document
rendering.

How
---

Deckhand uses `gabbi`_ to drive its integration tests. The entry point for
these tests is ``integration-tests.sh`` under ``tools`` directory.

The integration environment is deployed using `OpenStack-Helm`_ which
uses Helm to orchestrate deployment of Keystone, Barbican and other
pre-requisite services.

Usage
-----

These tests can be executed via ``./tools/integration-tests.sh <test-regex>``
from the command line, where ``<test-regex>`` is optional and if omitted all
available tests are run. ``sudo`` permissions are required. It is recommended
that these tests be executed inside a VM as a lot of data is pulled in (which
requires thorough clean up) during the deployment phase.

.. _gabbi: https://gabbi.readthedocs.io/en/latest/gabbi.html
.. _OpenStack-Helm: https://github.com/openstack/openstack-helm
