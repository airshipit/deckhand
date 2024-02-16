#!/usr/bin/env bash

# Script intended for running Deckhand integration tests, where integration
# is defined as the interaction between Deckhand and Keystone and Barbican.
# Installation dependency is openstack-helm-infra.
#
# USAGE: ./tools/integration-tests.sh <test-regex>

# TODO(fmontei): Use Ansible for all this.
# NOTE(fmontei): May have to automate the following installation guide for CI:
# https://docs.openstack.org/openstack-helm/latest/install/developer/requirements-and-host-config.html#host-configuration

set -xe

CURRENT_DIR="$(pwd)"
: "${OSH_INFRA_PATH:="../openstack-helm-infra"}"
: "${OSH_PATH:="../openstack-helm"}"
: "${TM_PATH:="../treasuremap"}"

export MAKE_CHARTS_OPENSTACK_HELM="${MAKE_CHARTS_OPENSTACK_HELM:-true}"
export MAKE_CHARTS_OSH_INFRA="${MAKE_CHARTS_OSH_INFRA:-true}"
export MAKE_CHARTS_ARMADA="${MAKE_CHARTS_ARMADA:-false}"
export MAKE_CHARTS_DECKHAND="${MAKE_CHARTS_DECKHAND:-false}"
export MAKE_CHARTS_SHIPYARD="${MAKE_CHARTS_SHIPYARD:-false}"
export MAKE_CHARTS_MAAS="${MAKE_CHARTS_MAAS:-false}"
export MAKE_CHARTS_PORTHOLE="${MAKE_CHARTS_PORTHOLE:-false}"
export MAKE_CHARTS_PROMENADE="${MAKE_CHARTS_PROMENADE:-false}"


function deploy_deckhand {
    set -xe

    export OS_CLOUD=openstack_helm

    cd ${CURRENT_DIR}


    # TODO(fmontei): Use Keystone bootstrap override instead.
    interfaces=("admin" "public" "internal")
    deckhand_endpoint="http://127.0.0.1:9000"

    if [ -z "$( openstack_client openstack service list --format value 2>/dev/null | grep deckhand )" ]; then
        openstack service create --enable --name deckhand deckhand 2>/dev/null
    fi

    for iface in ${interfaces[@]}; do
        if [ -z "$( openstack endpoint list --format value 2>/dev/null | grep deckhand | grep $iface )" ]; then
            openstack endpoint create --enable \
                --region RegionOne \
                deckhand $iface $deckhand_endpoint/api/v1.0 \
                     2>/dev/null
        fi
    done

    openstack service list | grep deckhand
    openstack endpoint list | grep deckhand

    gen_config false $deckhand_endpoint
    gen_paste false

    log_section "Running Deckhand via uwsgi."

    source ${CURRENT_DIR}/entrypoint.sh alembic upgrade head &
    # Give time for migrations to complete.
    sleep 10

    source ${CURRENT_DIR}/entrypoint.sh server &
    # Give the server a chance to come up. Better to poll a health check.
    sleep 10

    # NOTE(fmontei): Generate an admin token instead of hacking a policy
    # file with no permissions to test authN as well as authZ.
    export TEST_AUTH_TOKEN=$( openstack token issue --format value -c id  2>/dev/null )
    local test_barbican_url=$( openstack endpoint list --format value  2>/dev/null | grep barbican | grep public | awk '{print $7}' )

    if [[ $test_barbican_url == */ ]]; then
        test_barbican_url=$( echo $test_barbican_url | sed 's/.$//' )
    fi

    export TEST_BARBICAN_URL=$test_barbican_url
}


function run_tests {
    set +e

    export DECKHAND_TEST_DIR=${CURRENT_DIR}/deckhand/tests/integration/gabbits

    posargs=$@
    if [ ${#posargs} -ge 1 ]; then
        stestr --test-path deckhand/tests/common/ run --verbose --serial --slowest --force-subunit-trace --color $1
    else
        stestr --test-path deckhand/tests/common/ run --verbose --serial --slowest --force-subunit-trace --color
    fi
    TEST_STATUS=$?

    set -e

    if [ "x$TEST_STATUS" = "x0" ]; then
        log_section Done SUCCESS
    else
        log_section Done FAILURE
        exit $TEST_STATUS
    fi
}


source ${CURRENT_DIR}/tools/common-tests.sh

export AIRSHIP_DECKHAND_DATABASE_URL=${PIFPAF_POSTGRESQL_URL}

# Deploy Deckhand.
deploy_deckhand

run_tests "$@"
