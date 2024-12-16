#!/usr/bin/env bash
set -xe

RES=$(find . \
  -not -path "*/\.*" \
  -not -path "*/venv/*" \
  -not -path "*/venv3/*" \
  -not -path "*/tmp.*" \
  -not -path "*/*.egg-info/*" \
  -not -path "*/releasenotes/build/*" \
  -not -path "*/doc/build/*" \
  -not -path "*/doc/source/images/*" \
  -not -path "*/keybd_*.png" \
  -not -name "*.tgz" \
  -not -name "*.html" \
  -not -name "favicon_32.png" \
  -not -name "*.pyc" \
  -not -path "*/cover/*" \
  -type f -exec egrep -l " +$" {} \;)

if [[ -n $RES ]]; then
  exit 1
fi
