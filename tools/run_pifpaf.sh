#!/usr/bin/env bash

# This script is used for guaranteeing that `pifpaf` returns non-zero codes
# upon test failure.

function cleanup {
  set +e
  pifpaf_stop || deactivate
}

trap cleanup EXIT

# Instantiate an ephemeral PostgreSQL DB and print out the `pifpaf` environment
# variables for debugging purposes.
set -ex
if [ -z $(which pg_config) ]; then
    sudo apt-get install libpq-dev postgresql -y
fi

eval `pifpaf run postgresql`
env | grep PIFPAF
set +ex

set -eo pipefail

TESTRARGS=$1

stestr run --concurrency=1 --slowest $TESTRARGS
