Deckhand
========
A foundational python REST YAML processing engine providing data and secrets
management to other platform services.

To run::

	$ sudo pip install uwsgi
	$ virtualenv -p python3 /var/tmp/deckhand
	$ . /var/tmp/deckhand/bin/activate
	$ sudo pip install .
	$ uwsgi --http :9000 -w deckhand.deckhand --callable deckhand --enable-threads -L
