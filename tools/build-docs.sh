#!/usr/bin/env bash

# Builds documentation and generates documentation diagrams from .uml
# files. Must be run from root project directory.

set -ex

# Generate documentation.
rm -rf doc/build doc/source/contributor/api/ releasenotes/build
sphinx-apidoc -o doc/api deckhand
sphinx-build -W -b html doc/source doc/build/html
