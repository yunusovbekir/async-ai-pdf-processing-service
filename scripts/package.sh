#!/usr/bin/env bash
# Build submission.zip from the committed tree (HEAD): untracked/ignored files such as
# .env, .venv, node_modules and caches are never included.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
if ! git diff --quiet HEAD --; then
  echo "warning: uncommitted changes are NOT included in the archive" >&2
fi
git archive --format=zip -o submission.zip HEAD
echo "created submission.zip ($(du -h submission.zip | cut -f1))"
