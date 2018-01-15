#!/usr/bin/env bash

# This script is used for guaranteeing that `pifpaf` returns non-zero codes
# upon test failure.

function cleanup {
    pifpaf_stop
}

trap cleanup EXIT

# Instantiate an ephemeral PostgreSQL DB and print out the `pifpaf` environment
# variables for debugging purposes.
set -ex
eval `pifpaf run postgresql`
env | grep PIFPAF
set +ex

set -eo pipefail

TESTRARGS=$1

python setup.py testr --slowest --testr-args="--subunit --concurrency=1 $TESTRARGS" | subunit-trace -f
