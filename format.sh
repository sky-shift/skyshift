#!/usr/bin/env bash
# YAPF Formatter, adapted from Ray and Skypilot.
#
# Usage:
#    # Do work and commit your work.
#    # Format files that differ from origin/main.
#    bash format.sh
#    # Format all files.
#    bash format.sh --all
#    # Format individual files.
#    bash format.sh --files <filenames>
#    # Commit changed files with message 'Run yapf and pylint'
#
# YAPF + Clang formatter (if installed). This script formats all changed files from the last mergebase.
# Run this locally before pushing changes for review.

# Cause the script to exit if a single command fails
set -eo pipefail

# This stops git rev-parse from failing if we run this from the .git directory
builtin cd "$(dirname "${BASH_SOURCE:-$0}")"
ROOT="$(git rev-parse --show-toplevel)"
builtin cd "$ROOT" || exit 1

#==============================================================================#
# Checking Formatter and Linter Versions
YAPF_VERSION=$(yapf --version | awk '{print $2}')
PYLINT_VERSION=$(pylint --version | head -n 1 | awk '{print $2}')
PYLINT_QUOTES_VERSION=$(pip list | grep pylint-quotes | awk '{print $2}')
MYPY_VERSION=$(mypy --version | awk '{print $2}')

# Params: tool name, tool version, required version
tool_version_check() {
    if [[ $2 != $3 ]]; then
        echo "Wrong $1 version installed: $3 is required, not $2."
        exit 1
    fi
}

tool_version_check "yapf" $YAPF_VERSION "0.32.0"
tool_version_check "pylint" $PYLINT_VERSION "2.8.2"
tool_version_check "pylint-quotes" $PYLINT_QUOTES_VERSION "0.2.3"
tool_version_check "mypy" "$MYPY_VERSION" "1.8.0"

#==============================================================================#
# Run Yapf
YAPF_FLAGS=(
    '--recursive'
    '--parallel'
)

YAPF_EXCLUDES=(
)

# Format specified files
format() {
    yapf --in-place "${YAPF_FLAGS[@]}" "$@"
}

# Format files that differ from main branch. Ignores dirs that are not slated
# for autoformat yet.
format_changed() {
    # The `if` guard ensures that the list of filenames is not empty, which
    # could cause yapf to receive 0 positional arguments, making it hang
    # waiting for STDIN.
    #
    # `diff-filter=ACM` and $MERGEBASE is to ensure we only format files that
    # exist on both branches.
    MERGEBASE="$(git merge-base origin/main HEAD)"

    if ! git diff --diff-filter=ACM --quiet --exit-code "$MERGEBASE" -- '*.py' '*.pyi' &>/dev/null; then
        git diff --name-only --diff-filter=ACM "$MERGEBASE" -- '*.py' '*.pyi' | xargs -P 5 \
             yapf --in-place "${YAPF_EXCLUDES[@]}" "${YAPF_FLAGS[@]}"
    fi

}

# Format all files
format_all() {
    yapf --in-place "${YAPF_FLAGS[@]}" "${YAPF_EXCLUDES[@]}" api_server examples skyflow
}

## This flag formats individual files. --files *must* be the first command line
## arg to use this option.
if [[ "$1" == '--files' ]]; then
   format "${@:2}"
   # If `--all` is passed, then any further arguments are ignored and the
   # entire python directory is formatted.
elif [[ "$1" == '--all' ]]; then
   format_all
else
   # Format only the files that changed in last commit.
   format_changed
fi
echo '[Done] Skyshift yapf'

#==============================================================================#
# Run Isort
ISORT_YAPF_EXCLUDES=(
)

echo 'Skyshift isort:'
isort api_server skyflow  "${ISORT_YAPF_EXCLUDES[@]}"
echo '[Done] Skyshift isort:'

#==============================================================================#
# Run mypy
echo 'SkyPilot mypy:'
mypy api_server skyflow --show-traceback
echo '[Done] Skyshift mypy'

#==============================================================================#
# Run Pylint
echo 'Skyshift Pylint:'
pylint --load-plugins pylint_quotes --disable invalid-string-quote,duplicate-code skyflow api_server examples
echo '[Done] Skyshift Pylint'

#==============================================================================#

if ! git diff --quiet &>/dev/null; then
    echo 'Reformatted files. Please review and stage the changes.'
    echo 'Changes not staged for commit:'
    echo
    git --no-pager diff --name-only

    exit 1
fi
