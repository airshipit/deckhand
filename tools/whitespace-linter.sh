#!/usr/bin/env bash
set -xe

RES=$(find . \
  -not -path "*/\.*" \
  -not -path "*/*.egg-info/*" \
  -not -path "*/releasenotes/build/*" \
  -not -path "*/doc/build/*" \
  -not -path "*/doc/source/images/*" \
  -not -name "*.tgz" \
  -type f -exec egrep -l " +$" {} \;)

if [[ -n $RES ]]; then
  exit 1
fi
