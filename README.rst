========
Deckhand
========

|Doc Status|

Deckhand is a storage service for YAML-based configuration documents, which are
managed through version control and automatically validated. Deckhand provides
users with a variety of different document types that describe complex
configurations using the features listed below.

Find more documentation for Deckhand on `Read the Docs <https://deckhand.readthedocs.io/>`_.

Core Responsibilities
=====================

* layering - helps reduce duplication in configuration by applying the notion
  of inheritance to documents
* substitution - provides separation between secret data and other
  configuration data for security purposes and reduces data duplication by
  allowing common data to be defined once and substituted elsewhere dynamically
* revision history - maintains well-defined collections of documents within
  immutable revisions that are meant to operate together, while providing the
  ability to rollback to previous revisions
* validation - allows services to implement and register different kinds of
  validations and report errors
* secret management - leverages existing OpenStack APIs -- namely
  `Barbican`_ -- to reliably and securely store sensitive data

.. _Barbican: https://docs.openstack.org/barbican/latest/api/

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

Integration Points
==================

Deckhand has the following integration points:

  * `Barbican (OpenStack Key Manager) <https://github.com/openstack/barbican>`_
    provides secure storage for sensitive data.
  * `Keystone (OpenStack Identity service) <https://github.com/openstack/keystone>`_
    provides authentication and support for role based authorization.
  * `PostgreSQL <https://www.postgresql.org>`_ is used to persist information
    to correlate workflows with users and history of workflow commands.

  .. note::

    Currently, other database back-ends are not supported.

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

.. |Doc Status| image:: https://readthedocs.org/projects/deckhand/badge/?version=latest
   :target: http://deckhand.readthedocs.io/
