# Remove _SCRIPTS_DIR from set_env.sh

`_SCRIPTS_DIR` (`$_GIT_ROOT/scripts`) had zero usages in the codebase.
Removed the dead export from `set_env.sh`.
