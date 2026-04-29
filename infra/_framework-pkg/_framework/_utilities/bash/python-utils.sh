#!/bin/bash

# GOAL
# - Make it easy to use Python and tools that use Python, like Ansible.
#
# NOTES
# - To set up Python in a virtual environment, run
#    _activate_python_locally
# - To do the same and then install Ansible, run
#    _activate_ansible_locally

# Aggressively catch and report errors
set -euo pipefail
function handle_error {
    local exit_status=$?
    echo "An error occurred on line ${LINENO:-not-defined}: ${BASH_COMMAND:-not-defined}"
    exit $exit_status
}
trap handle_error ERR

# Be self-contained. Use an isolated python and ansible installation
function _use_python_venv() {
    _VENV_DIR_PARENT="$1"

    _VENV_DIR="$_VENV_DIR_PARENT/.venv"

    if [ -e "$_VENV_DIR" ]; then
        # Validate that the venv's embedded path matches the current location.
        # uv venv hardcodes the absolute path into bin/activate; after a directory
        # rename/move the embedded path becomes stale and uv pip install fails.
        _venv_embedded_path=$(grep -m1 'VIRTUAL_ENV=' "$_VENV_DIR/bin/activate" \
            | sed "s/.*VIRTUAL_ENV=['\"]\\(.*\\)['\"].*/\\1/")
        if [ "$_venv_embedded_path" != "$_VENV_DIR" ]; then
            echo "Stale venv at $_VENV_DIR (embedded path: $_venv_embedded_path) — recreating"
            rm -rf "$_VENV_DIR"
        fi
    fi

    if [ ! -e "$_VENV_DIR" ]; then
        echo "Installing Python virtual environment in $_VENV_DIR"
        if [ -n "${PYTHON_VERSION+x}" ]; then
          uv venv $_VENV_DIR --python $PYTHON_VERSION
        else
          uv venv $_VENV_DIR
        fi
    fi

    # Activate Python venv
    . $_VENV_DIR/bin/activate
}

function _install_ansible() {
    _VENV_DIR_PARENT="$1"

    if ! command -v pip | grep 'venv' &> /dev/null; then
        echo "Installing pip"
        uv pip install --upgrade pip
    fi

    if ! command -v ansible | grep 'venv' &> /dev/null; then
        echo "Installing Ansible and Ansible-Galaxy"
        uv pip install ansible
    fi
}

# This is equivalent to "pip install -r requirements.txt"
# But:
# - it's faster on subsequent runs.
# - output is cleaner (e.g. the screen is not filled with stuff when nothing is installed)
function _pip_install_requirements() {
    _REQUIREMENTS_FILE="$1"

    [ -f "$_REQUIREMENTS_FILE" ] || return 0

    output=$(uv pip install -r "$_REQUIREMENTS_FILE" 2>&1)
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo "$output"
        exit $exit_code
    fi
}

# This will:
# - Create a Python virtual environment (.venv).
# - Activate the venv
# - Install the requirements file
function _activate_python_locally() {
    # Parent of the Python Virtual Environment.
    _VENV_DIR_PARENT="$1"

    # Install and activate .venv
    _use_python_venv "$_VENV_DIR_PARENT"

    # Install requirements
    _REQUIREMENTS_FILE="$_VENV_DIR_PARENT/requirements.txt"
    _pip_install_requirements "$_REQUIREMENTS_FILE"
    # Also, install the requirements file in the current directory
    _pip_install_requirements "$(pwd)/requirements.txt"

    # Ensure python3 is in path
    command -v "python3" >/dev/null
}

# Set up the local environment in an isolated way to run Ansible
#
# This will:
# - Call _activate_python_locally
# - Install Ansible
function _activate_ansible_locally() {
    # Parent of the Python Virtual Environment.
    # Package (version) conflicts will eventually occur if we share environments.
    _VENV_DIR_PARENT="$1"

    _activate_python_locally "$_VENV_DIR_PARENT"

    # Install Ansible
    _install_ansible "$_VENV_DIR_PARENT"

    # Tell Ansible to use the venv python
    export ANSIBLE_PYTHON_INTERPRETER="${_VENV_DIR_PARENT}/.venv/bin/python3"

    # Confirm ansible is in PATH
    command -v "ansible" >/dev/null
}
