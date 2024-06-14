#!/usr/bin/env bash

# YAPF Formatter, adapted from Ray and Skypilot.

USAGE="
Usage: format.sh [OPTIONS] [FILENAMES...]

If no filenames are given, format all files that differ from origin/main.

Options:
  --all      Format all files
  --check    Report errors but do not modify the files

Examples:
  Format files that differ from origin/main   ./format.sh
  Format files a.txt and b/c.txt              ./format.sh a.txt b/c.txt
  Format all files in the repository          ./format.sh --all
  Only check the formatting (like the CI)     ./format.sh --all --check"

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

# Parse CLI arguments (based on https://stackoverflow.com/a/14203146)

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            ALL=true
            shift
            ;;
        --check)
            CHECK=true
            shift
            ;;
        -*|--*)
            echo "Error: unknown option $1"
            echo "$USAGE"
            exit 1
            ;;
        *)
            FILES=("${@:1}")
            break
    esac
done

if [ "$ALL" = true ] ; then
    FILES=("api_server" "examples" "skyflow")
elif [ -z "${FILES}" ]; then
    MERGEBASE="$(git merge-base origin/main HEAD)"
    FILES="$(git diff --name-only --diff-filter=ACM "$MERGEBASE" -- '*.py' '*.pyi')"
fi

#==============================================================================#
# Run Yapf

echo '[SkyShift] Running yapf'
if [ "$CHECK" = true ] ; then
    ARGS=("--diff")
else
    ARGS=("--in-place")
fi
printf "%s\n" "${FILES[@]}" | xargs -P 5 yapf "${ARGS[@]}" --recursive --parallel

#==============================================================================#
# Run Isort

echo '[SkyShift] Running isort'
if [ "$CHECK" = true ] ; then
    ARGS=("--check-only" "--diff" "--color")
else
    ARGS=()
fi
printf "%s\n" "${FILES[@]}" | xargs -P 5 isort "${ARGS[@]}"

#==============================================================================#
# Run mypy

echo '[SkyShift] Running mypy'
mypy --show-traceback api_server skyflow

#==============================================================================#
# Run Pylint

echo '[SkyShift] Running pylint'
printf "%s\n" "${FILES[@]}" | xargs -P 5 pylint \
    --load-plugins pylint_quotes \
    --disable invalid-string-quote,duplicate-code \
    --max-line-length=120

#==============================================================================#

echo '[SkyShift] Completed all checks!'

if ! git diff --quiet &>/dev/null; then
    echo
    echo 'Reformatted files. Please review and stage the changes.'
    echo
    echo 'Changes not staged for commit:'
    git --no-pager diff --name-only

    exit 1
fi
