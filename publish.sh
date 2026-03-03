#!/usr/bin/env bash
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILLS_DIR="$CODEX_HOME/skills"
REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
  cat <<'EOF'
Usage:
  publish.sh <skill-name> [--as <published-name>] [--force]   Move skill into repo, symlink back
  publish.sh --link-all                                       Create symlinks for all skills in repo
  publish.sh --status                                         Show which published skills are symlinked

Examples:
  ./publish.sh execplan-improve                      Publish with same name
  ./publish.sh my-skill --as published-skill         Publish under a different name
  ./publish.sh --link-all                            After a fresh clone, wire up all symlinks
EOF
  exit 1
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_dirs() {
  [ -d "$SKILLS_DIR" ] || die "Missing skills dir: $SKILLS_DIR"
  [ -d "$REPO_DIR" ] || die "Missing repo dir: $REPO_DIR"
}

validate_name() {
  local name="$1"
  local label="$2"
  [ -n "$name" ] || die "$label is empty"
  case "$name" in
    */*) die "$label must not contain '/': $name" ;;
  esac
}

real_dir() {
  local path="$1"
  (cd "$path" 2>/dev/null && pwd -P)
}

build_symlink_map() {
  local tmp
  tmp="$(mktemp)"
  for candidate in "$SKILLS_DIR"/*; do
    [ -L "$candidate" ] || continue
    [ -d "$candidate" ] || continue
    local resolved
    resolved="$(real_dir "$candidate")" || continue
    printf '%s\t%s\n' "$resolved" "$(basename "$candidate")" >>"$tmp"
  done
  echo "$tmp"
}

link_one() {
  local skill_name="$1"
  local published_name="$2"
  local force="${3:-0}"
  local source="$SKILLS_DIR/$skill_name"
  local target="$REPO_DIR/$published_name"

  validate_name "$skill_name" "skill name"
  validate_name "$published_name" "published name"

  if [ -L "$source" ] || [ -e "$source" ]; then
    if [ -L "$source" ]; then
      local resolved expected
      resolved="$(real_dir "$source" || true)"
      expected="$(real_dir "$target" || true)"
      if [ -n "$resolved" ] && [ -n "$expected" ] && [ "$resolved" = "$expected" ]; then
        echo "  ✓ $skill_name → already symlinked"
        return
      fi
      if [ "$force" -eq 1 ]; then
        rm "$source"
      else
        die "$skill_name exists as a symlink but does not point at $published_name (use --force to relink)"
      fi
    else
      [ -d "$source" ] || die "$skill_name exists but is not a directory: $source"
    fi
  fi

  if [ -d "$source" ]; then
    echo "  Moving $source → $target"
    if [ -e "$target" ]; then
      if [ "$force" -eq 1 ]; then
        local backup
        backup="$target.__backup__$(date +%Y%m%d%H%M%S)"
        mv "$target" "$backup"
        echo "  Existing repo copy moved aside: $backup"
      else
        die "Repo already has $published_name (use --force to move it aside)"
      fi
    fi
    mv "$source" "$target"
  elif [ ! -d "$target" ]; then
    die "$skill_name not found in $SKILLS_DIR or $REPO_DIR"
  fi

  ln -s "$target" "$source"
  echo "  ✓ $skill_name → symlinked to $published_name"
}

link_all() {
  require_dirs
  echo "Linking all published skills..."
  local map_file
  map_file="$(build_symlink_map)"
  for dir in "$REPO_DIR"/*; do
    [ -d "$dir" ] || continue
    local published_name
    published_name=$(basename "$dir")
    local real_repo_path
    real_repo_path="$(real_dir "$dir")"

    local linked_name
    linked_name="$(awk -v k="$real_repo_path" -F'\t' '$1==k {print $2; exit}' "$map_file")"
    if [ -n "$linked_name" ]; then
      echo "  ✓ $linked_name → already symlinked to $published_name"
      continue
    fi

    local skill_name="$published_name"
    if [ -e "$SKILLS_DIR/$skill_name" ] && [ ! -L "$SKILLS_DIR/$skill_name" ]; then
      if [ -d "$SKILLS_DIR/$skill_name" ]; then
        echo "  ⚠ $published_name  ←  $published_name exists as a real directory (duplicated); skipping"
        continue
      fi
      die "$published_name exists but is not a directory or symlink: $SKILLS_DIR/$skill_name"
    else
      ln -s "$REPO_DIR/$published_name" "$SKILLS_DIR/$skill_name"
      echo "  ✓ $published_name → symlink created"
    fi
  done
  rm -f "$map_file"
  echo "Done."
}

status() {
  require_dirs
  echo "Published skills status:"
  local map_file
  map_file="$(build_symlink_map)"
  for dir in "$REPO_DIR"/*; do
    [ -d "$dir" ] || continue
    local published_name
    published_name=$(basename "$dir")
    local real_repo_path
    real_repo_path="$(real_dir "$dir")"

    local linked_name
    linked_name="$(awk -v k="$real_repo_path" -F'\t' '$1==k {print $2; exit}' "$map_file")"
    if [ -n "$linked_name" ]; then
      echo "  ✓ $published_name  ←  $linked_name (symlinked)"
      continue
    fi

    if [ -d "$SKILLS_DIR/$published_name" ] && [ ! -L "$SKILLS_DIR/$published_name" ]; then
      echo "  ⚠ $published_name  ←  $published_name (DUPLICATED, not symlinked)"
    else
      echo "  ✗ $published_name  ←  no symlink in skills/"
    fi
  done
  rm -f "$map_file"
}

if [ $# -eq 0 ]; then
  usage
fi

case "$1" in
  --link-all) link_all ;;
  --status)   status ;;
  --help|-h)  usage ;;
  *)
    require_dirs
    skill_name="$1"
    shift
    published_name="$skill_name"
    force=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --as)
          [ -n "${2:-}" ] || usage
          published_name="$2"
          shift 2
          ;;
        --force)
          force=1
          shift
          ;;
        *)
          usage
          ;;
      esac
    done
    link_one "$skill_name" "$published_name" "$force"
    ;;
esac
