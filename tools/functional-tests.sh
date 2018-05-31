#!/usr/bin/env bash

# Script intended for running Deckhand functional tests via gabbi for
# developers. Dependencies include gabbi, pifpaf and uwsgi.
#
# Usage: pifpaf run postgresql -- tools/functional-tests.sh

set -xe

CURRENT_DIR="$(pwd)"


function cleanup_deckhand {
    set +e

    # Kill PostgreSQL if it is still running.
    pifpaf_stop || deactive

    # Kill uwsgi service if it is still running.
    PID=$( sudo netstat -tulpn | grep ":9000" | head -n 1 | awk '{print $NF}' )
    if [ -n $PID ]; then
        PID=${PID%/*}
        sudo kill -9 $PID
    fi
}


trap cleanup_deckhand EXIT


function deploy_deckhand {
    gen_config true "127.0.0.1:9000"
    gen_paste true

    log_section "Running Deckhand via uwsgi."

    source ${CURRENT_DIR}/entrypoint.sh alembic upgrade head &
    # Give time for migrations to complete.
    sleep 10

    source ${CURRENT_DIR}/entrypoint.sh server &
    # Give the server a chance to come up. Better to poll a health check.
    sleep 10
}


export AIRSHIP_DECKHAND_DATABASE_URL=${PIFPAF_POSTGRESQL_URL}

# Deploy Deckhand and PostgreSQL and run tests.
source ${CURRENT_DIR}/tools/common-tests.sh
deploy_deckhand

log_section "Running tests."

export DECKHAND_TEST_DIR=${CURRENT_DIR}/deckhand/tests/functional/gabbits

set +e
posargs=$@
if [ ${#posargs} -ge 1 ]; then
    py.test -k $1 -svx ${CURRENT_DIR}/deckhand/tests/common/test_gabbi.py
else
    py.test -svx ${CURRENT_DIR}/deckhand/tests/common/test_gabbi.py
fi
TEST_STATUS=$?
set -e

if [ "x$TEST_STATUS" = "x0" ]; then
    log_section Done SUCCESS
else
    log_section Deckhand Server Log
    log_section Done FAILURE
    exit ${TEST_STATUS}
fi
