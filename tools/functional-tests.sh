#!/usr/bin/env bash

# Script intended for running Deckhand functional tests via gabbi. Requires
# Docker CE (at least) to run.

set -xe

# Meant for capturing output of Deckhand image. This requires that logging
# in the image be set up to pipe everything out to stdout/stderr.
STDOUT=$(mktemp)

# NOTE(fmontei): `DECKHAND_IMAGE` should only be specified if the desire is to
# run Deckhand functional tests against a specific Deckhand image, which is
# useful for CICD (as validating the image is vital). However, if the
# `DECKHAND_IMAGE` is not specified, then this implies that the most current
# version of the code should be used, which is in the repo itself.
DECKHAND_IMAGE=${DECKHAND_IMAGE:-}
ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source $ROOTDIR/common-tests.sh


function cleanup_deckhand {
    set +e

    if [ -n "$POSTGRES_ID" ]; then
        sudo docker stop $POSTGRES_ID
    fi

    if [ -n "$DECKHAND_ID" ]; then
        sudo docker stop $DECKHAND_ID
    fi

    rm -rf $CONF_DIR

    if [ -z "$DECKHAND_IMAGE" ]; then
        # Kill uwsgi service if it is still running.
        PID=$( sudo netstat -tulpn | grep ":9000" | head -n 1 | awk '{print $NF}' )
        if [ -n $PID ]; then
            PID=${PID%/*}
            sudo kill -9 $PID
        fi
    fi
}


trap cleanup_deckhand EXIT


function deploy_deckhand {
    gen_config true "127.0.0.1:9000"
    gen_paste true

    if [ -z "$DECKHAND_IMAGE" ]; then
        log_section "Running Deckhand via uwsgi."

        alembic upgrade head
        # NOTE(fmontei): Deckhand's database is not configured to work with
        # multiprocessing. Currently there is a data race on acquiring shared
        # SQLAlchemy engine pooled connection strings when workers > 1. As a
        # workaround, we use multiple threads but only 1 worker. For more
        # information, see: https://github.com/att-comdev/deckhand/issues/20
        export DECKHAND_API_WORKERS=1
        export DECKHAND_API_THREADS=4
        source $ROOTDIR/../entrypoint.sh server &
    else
        log_section "Running Deckhand via Docker."

        # If container is already running, kill it.
        DECKHAND_ID=$(sudo docker ps --filter ancestor=$DECKHAND_IMAGE --format "{{.ID}}")
        if [ -n "$DECKHAND_ID" ]; then
            sudo docker stop $DECKHAND_ID
        fi

        sudo docker run \
            --rm \
            --net=host \
            -v $CONF_DIR:/etc/deckhand \
            $DECKHAND_IMAGE alembic upgrade head &> $STDOUT &
        sudo docker run \
            --rm \
            --net=host \
            -p 9000:9000 \
            -v $CONF_DIR:/etc/deckhand \
            $DECKHAND_IMAGE server &> $STDOUT &

        DECKHAND_ID=$(sudo docker ps | grep deckhand | awk '{print $1}')
        echo $DECKHAND_ID
    fi

    # Give the server a chance to come up. Better to poll a health check.
    sleep 5
}


# Deploy Deckhand and PostgreSQL and run tests.
deploy_postgre
deploy_deckhand

log_section Running tests

# Create folder for saving HTML test results.
mkdir -p $ROOTDIR/results

export DECKHAND_TESTS_DIR=${ROOTDIR}/../deckhand/tests/functional/gabbits

set +e
posargs=$@
if [ ${#posargs} -ge 1 ]; then
    py.test -k $1 -svx $( dirname $ROOTDIR )/deckhand/tests/common/test_gabbi.py --html=results/index.html
else
    py.test -svx $( dirname $ROOTDIR )/deckhand/tests/common/test_gabbi.py --html=results/index.html
fi
TEST_STATUS=$?
set -e

if [ "x$TEST_STATUS" = "x0" ]; then
    log_section Done SUCCESS
else
    log_section Deckhand Server Log
    cat $STDOUT
    log_section Done FAILURE
    exit $TEST_STATUS
fi
