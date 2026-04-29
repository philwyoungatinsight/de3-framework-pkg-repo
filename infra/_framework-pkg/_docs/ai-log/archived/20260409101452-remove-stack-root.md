# Remove _STACK_ROOT from set_env.sh

`_STACK_ROOT` was identical to `_GIT_ROOT` and had zero usages anywhere in the
codebase. Removed the dead export from `set_env.sh`.
