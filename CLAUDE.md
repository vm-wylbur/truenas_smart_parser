# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# CLAUDE.md

# Development Guidelines for resource-utils

## 1. Code Changes
- NO changes to main code without explicit approval
- Always propose changes before implementing
- Exploratory commands (ls, find, grep, cat, etc.) can be run freely without approval
- Stop and ask before making any code changes
- Comments explain WHY, not WHAT
- Keep functions focused and single-purpose
- Always define constants in ALL_CAPS and use appropriate frozenset, frozen=True, typing.Final, MappingProxyType, typing.Literal, typing.ReadOnly or similar features to prevent changes
- Assume python >=3.13 respecting this version's type annotation and other features
- Follow existing code style and patterns
- Seek minimal code refactors unless discussed with me first

## 2. Development Flow
- Take one step at a time
- Each step should be small and verifiable
- Check existing code! Don't propose new code until you confirm that we don't have that functionality already
- Keep the code **DRY**
- Consider edge cases before marking a task complete
- Be cautious with system operations (ZFS, rsync, etc.) - use dry-run modes when available

## 3. Communication
- Keep communication direct and professional without unnecessary politeness
- Ask clarifying questions when specifications are unclear
- We operate as peers with mutual respect
- Keep proposals and their rationale together
- Be explicit about assumptions
- Flag potential backwards compatibility issues
- Sign commit messages "By PB & Claude"
- Remove any "Generated" lines and change to "Co-authored-by: Claude and PB"

## 4. File Headers
Every file should begin with:
```
# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# relative/path/to/file  <-- relative to git root
```
use the appropriate comment format, not always `#`, could be <!-- comment --> 

## 5. System Utilities Considerations
- These utilities often require root/sudo access
- Always verify destructive operations have safeguards
- Consider security implications of API keys, SSH operations
- Respect existing lock file mechanisms to prevent concurrent runs
- Be mindful of network operations and remote system interactions
- Use dry-run modes for testing when available
- Log operations comprehensively for troubleshooting


## 7. Code Style & Formatting
- Line length: 79 characters
- Use black with `--line-length 79`
- Import ordering (3 groups with blank lines between):
  1. Python builtins
  2. External dependencies
  3. Local modules (like hrdaglib)
- Google-style docstrings
- Type hints for all functions and methods

## 8. Error Handling & Logging
- Use loguru for logging
- Use Typer for CLI exits and error messages
- Structured logging with appropriate levels
- Clear, actionable error messages
- Log file paths configured via environment/config files

## 9. Git Workflow
- Check for pre-commit hooks if available
- Descriptive commit messages explaining WHY, not just what

## 10. Configuration Management
- Use environment files (.env) for sensitive data (API keys, passwords)
- TOML files for general configuration
- Keep configuration separate from code
- Document all required environment variables

