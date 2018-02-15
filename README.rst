========
Deckhand
========

Deckhand is a storage service for YAML-based configuration documents, which are
managed through version control and automatically validated. Deckhand provides
users with a variety of different document types that describe complex
configurations using the features listed below.

Core Responsibilities
=====================

* layering - helps reduce duplication in configuration while maintaining
  auditability across many sites
* substitution - provides separation between secret data and other
  configuration data, while allowing a simple interface for clients
* revision history - improves auditability and enables services to provide
  functional validation of a well-defined collection of documents that are
  meant to operate together
* validation - allows services to implement and register different kinds of
  validations and report errors

Getting Started
===============

For more detailed installation and setup information, please refer to the
`Getting Started <http://deckhand.readthedocs.io/en/latest/getting-started.html>`_
guide.

Testing
-------

Automated Testing
^^^^^^^^^^^^^^^^^

To run unit tests using sqlite, execute:

::

    $ tox -epy27
    $ tox -epy35

against a py27- or py35-backed environment, respectively. To run individual
unit tests, run:

::

    $ tox -e py27 -- deckhand.tests.unit.db.test_revisions

for example.

To run functional tests:

::

    $ tox -e functional

You can also run a subset of tests via a regex:

::

    $ tox -e functional -- gabbi.suitemaker.test_gabbi_document-crud-success-multi-bucket

Intgration Points
=================

Deckhand has the following integration points:

  * `Keystone (OpenStack Identity service) <https://github.com/openstack/keystone>`_
    provides authentication and support for role based authorization.
  * `PostgreSQL <https://www.postgresql.org>`_ is used to persist information
    to correlate workflows with users and history of workflow commands.

  .. note::

    Currently, other database backends are not supported.

Though, being a low-level service, has many other UCP services that integrate
with it, including:

  * `Drydock <https://github.com/att-comdev/drydock>`_ is orchestrated by
    Shipyard to perform bare metal node provisioning.
  * `Promenade <https://github.com/att-comdev/promenade>`_ is indirectly
    orchestrated by Shipyard to configure and join Kubernetes nodes.
  * `Armada <https://github.com/att-comdev/armada>`_ is orchestrated by
    Shipyard to deploy and test Kubernetes workloads.

Further Reading
===============

`Undercloud Platform (UCP) <https://github.com/att-comdev/ucp-integration>`_.
