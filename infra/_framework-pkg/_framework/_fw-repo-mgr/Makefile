.PHONY=default
default: |build

.PHONY=FORCE
FORCE:

.PHONY=build
build: FORCE
	./fw-repo-mgr --build

.PHONY=validate
validate: FORCE
	./fw-repo-mgr --validate

.PHONY=status
status: FORCE
	./fw-repo-mgr --status
