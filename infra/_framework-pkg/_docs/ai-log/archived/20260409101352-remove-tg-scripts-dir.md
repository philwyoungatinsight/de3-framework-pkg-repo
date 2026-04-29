# Remove _TG_SCRIPTS_DIR from set_env.sh

`_TG_SCRIPTS_DIR` was identical to `_INFRA_DIR` (`$_GIT_ROOT/infra`) and had zero
usages anywhere in the codebase. Removed the dead export from `set_env.sh`.
