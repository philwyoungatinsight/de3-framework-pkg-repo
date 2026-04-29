#!/bin/bash

# Goal
#   Collect some useful re-usable utilities

# Aggressively catch and report errors
set -euo pipefail
function handle_error {
    local exit_status=$?
    echo "An error occurred on line ${LINENO:-not-defined}: ${BASH_COMMAND:-not-defined}"
    exit $exit_status
}
trap handle_error ERR

# Path to this script
INIT_SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

# Pull in utility functions
. $INIT_SCRIPT_DIR/framework-utils.sh
. $INIT_SCRIPT_DIR/python-utils.sh
