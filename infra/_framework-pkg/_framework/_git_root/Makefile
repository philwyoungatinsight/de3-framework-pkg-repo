.PHONY: all bootstrap build clean clean-all setup seed test

# Full first-time setup + full build. Bootstrap is automatic inside './run --build'.
all: build

# Explicit bootstrap (idempotent): clone/update de3-runner and create infra/_framework-pkg symlink.
bootstrap:
	@./run --bootstrap

build:
	@./run --sync-packages
	@./run --build

clean:
	@./run --clean

clean-all:
	@./run --clean-all

setup:
	@./run --setup-packages

seed:
	@./run --seed-packages

test:
	@./run --test
