Deckhand
========
A foundational python REST YAML processing engine providing data and secrets
management to other platform services.

To generate a configuration file automatically::

	$ tox -e genconfig

Resulting deckhand.conf.sample file is output to
:path:etc/deckhand/deckhand.conf.sample

Copy the config file to a directory discoverably by ``oslo.conf``::

	$ cp etc/deckhand/deckhand.conf.sample ~/deckhand.conf

To setup an in-memory database for testing:

.. code-block:: ini

	[database]

	#
	# From oslo.db
	#

	# The SQLAlchemy connection string to use to connect to the database.
	# (string value)
	connection = sqlite:///:memory:

To run locally in a development environment::

	$ sudo pip install uwsgi
	$ virtualenv -p python3 /var/tmp/deckhand
	$ . /var/tmp/deckhand/bin/activate
	$ sudo pip install .
	$ sudo python setup.py install
	$ uwsgi --http :9000 -w deckhand.cmd --callable deckhand_callable --enable-threads -L
