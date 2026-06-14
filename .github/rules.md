# Development Rules & Conventions

## Git Commit Messages
- Use conventional commits.
- Use multi-line messages when the work is not trivial.
- When closing GitHub issues via a commit, use the `closes #X` format in the commit message.

## Build and Package Tooling
- Standardize on `uv` as the build, virtualenv, and package management tool.
- Use `uv sync` to install/synchronize dependencies.
- Prefix test, lint, format, and run commands with `uv run` in the Makefile and CLI operations.
