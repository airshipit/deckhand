#!/usr/bin/env bash

function log_section {
    set +x
    echo 1>&2
    echo 1>&2
    echo === $* === 1>&2
    set -x
}

set -ex


log_section Starting Postgres
POSTGRES_ID=$(
    sudo docker run \
        --detach \
        --publish :5432 \
        -e POSTGRES_DB=deckhand \
        -e POSTGRES_USER=deckhand \
        -e POSTGRES_PASSWORD=password \
            postgres:10
)

function cleanup {
    sudo docker stop $POSTGRES_ID
    kill %1
}

trap cleanup EXIT

POSTGRES_IP=$(
    sudo docker inspect \
        --format='{{ .NetworkSettings.Networks.bridge.IPAddress }}' \
            $POSTGRES_ID
)
POSTGRES_PORT=$(
    sudo docker inspect \
        --format='{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}' \
            $POSTGRES_ID
)


export DECKHAND_TEST_URL=http://localhost:9000
export DATABASE_URL=postgres://deckhand:password@$POSTGRES_IP:$POSTGRES_PORT/deckhand

log_section Creating config file
CONF_DIR=$(mktemp -d)

cat <<EOCONF > $CONF_DIR/deckhand.conf
[DEFAULT]
debug = true
use_stderr = true
[barbican]


[database]
# XXX For now, connection to postgres is not setup.
#connection = $DATABASE_URL
connection = sqlite://


[keystone_authtoken]
EOCONF

echo $CONF_DIR/deckhand.conf 1>&2
cat $CONF_DIR/deckhand.conf 1>&2

log_section Starting server
rm -f deckhand.log

uwsgi \
    --http :9000 \
    -w deckhand.cmd \
    --callable deckhand_callable \
    --enable-threads \
    -L \
    --pyargv "--config-file $CONF_DIR/deckhand.conf" &

# Give the server a chance to come up.  Better to poll a health check.
sleep 5

log_section Running tests

set +e
ostestr -c 1 $*
TEST_STATUS=$?
set -e

if [ "x$TEST_STATUS" = "x0" ]; then
    log_section Done SUCCESS
else
    log_section Deckhand Server Log
    cat deckhand.log
    log_section Done FAILURE
    exit $TEST_STATUS
fi
