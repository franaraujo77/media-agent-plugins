#!/usr/bin/env bash
set -euo pipefail

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found on PATH; skipping plugin validation." >&2
  exit 0
fi

repo_root="$(git rev-parse --show-toplevel)"
status=0

while IFS= read -r -d '' manifest; do
  plugin_dir="$(dirname "$(dirname "$manifest")")"
  echo "Validating $plugin_dir"
  if ! claude plugin validate "$plugin_dir"; then
    status=1
  fi
done < <(find "$repo_root/plugins" -mindepth 3 -maxdepth 3 -path '*/.claude-plugin/plugin.json' -print0)

exit "$status"
