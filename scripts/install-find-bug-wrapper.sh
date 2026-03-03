#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_SCRIPT="$SCRIPT_DIR/find-bug-pipeline.sh"

if [[ ! -f "$PIPELINE_SCRIPT" ]]; then
  echo "error: missing pipeline script: $PIPELINE_SCRIPT" >&2
  exit 1
fi
if [[ ! -x "$PIPELINE_SCRIPT" ]]; then
  chmod +x "$PIPELINE_SCRIPT"
fi

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "error: run this command inside a git repository" >&2
  exit 1
fi

wrapper_path="$repo_root/find-bug"
exclude_path="$repo_root/.git/info/exclude"

cat > "$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

exec "$PIPELINE_SCRIPT" "\$@"
EOF
chmod +x "$wrapper_path"

mkdir -p "$(dirname -- "$exclude_path")"
touch "$exclude_path"
if ! grep -Fxq "find-bug" "$exclude_path"; then
  printf '\n%s\n' "find-bug" >> "$exclude_path"
fi

echo "wrapper_installed=true"
echo "wrapper_path=$wrapper_path"
echo "exclude_path=$exclude_path"
