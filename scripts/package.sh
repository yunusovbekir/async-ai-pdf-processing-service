#!/usr/bin/env bash
# Build submission.zip from the committed tree (HEAD): untracked/ignored files such as
# .env, .venv, node_modules and caches are never included.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
if ! git diff --quiet HEAD --; then
  echo "warning: uncommitted changes are NOT included in the archive" >&2
fi
# Excluded: tasks.md, system-prompt.md, this script, and every dotfile/dot-directory
# at any depth except .env.example (a pathspec exclude cannot be re-included, so filter the list).
git ls-tree -r -z --name-only HEAD \
  | grep -zvE '^(tasks\.md|system-prompt\.md|scripts/package\.sh)$' \
  | grep -zE '^([^./][^/]*/)*(\.env\.example|[^./][^/]*)$' \
  | xargs -0 git archive --format=zip -o submission.zip HEAD --
echo "created submission.zip ($(du -h submission.zip | cut -f1))"
