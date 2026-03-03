#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF' >&2
usage: ./find-bug "<bug-hunt prompt>"

Example:
  ./find-bug "look deeply into how we manage dependencies"
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: required command not found: $cmd" >&2
    exit 1
  fi
}

resolve_path_in_worktree() {
  local path="$1"
  local worktree_dir="$2"
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
    return 0
  fi
  printf '%s/%s\n' "$worktree_dir" "$path"
}

slugify_prompt() {
  local prompt="$1"
  local slug
  slug="$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
  if [[ -z "$slug" ]]; then
    slug="bug-hunt"
  fi
  printf '%s\n' "${slug:0:48}"
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

user_prompt="$1"
if [[ -z "${user_prompt// }" ]]; then
  usage
  exit 1
fi

require_cmd git
require_cmd codex
require_cmd jq

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILLS_ROOT="$CODEX_HOME/skills"
USEFUL_SKILLS_ROOT="$CODEX_HOME/useful-codex-skills"
STREAM_LOGS="${FIND_BUG_STREAM_LOGS:-1}"
HEARTBEAT_SECONDS="${FIND_BUG_HEARTBEAT_SECONDS:-20}"

if [[ "$STREAM_LOGS" != "0" && "$STREAM_LOGS" != "1" ]]; then
  echo "error: FIND_BUG_STREAM_LOGS must be 0 or 1 (got: $STREAM_LOGS)" >&2
  exit 1
fi
if ! [[ "$HEARTBEAT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "error: FIND_BUG_HEARTBEAT_SECONDS must be an integer (got: $HEARTBEAT_SECONDS)" >&2
  exit 1
fi

skill_find="$SKILLS_ROOT/find-bug-generic/SKILL.md"
skill_improve="$SKILLS_ROOT/execplan-improve/SKILL.md"
skill_implement="$SKILLS_ROOT/implement-execplan/SKILL.md"

if [[ ! -f "$skill_find" ]]; then
  echo "error: missing skill: $skill_find" >&2
  echo "hint: cd $USEFUL_SKILLS_ROOT && ./publish.sh find-bug-generic" >&2
  exit 1
fi
if [[ ! -f "$skill_improve" ]]; then
  echo "error: missing skill: $skill_improve" >&2
  exit 1
fi
if [[ ! -f "$skill_implement" ]]; then
  echo "error: missing skill: $skill_implement" >&2
  exit 1
fi

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "error: current directory is not inside a git repository" >&2
  exit 1
fi

repo_name="$(basename "$repo_root")"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_id="findbug-${timestamp}-$$"
slug="$(slugify_prompt "$user_prompt")"
branch_name="codex/find-bug-${slug}-${timestamp}"
base_ref="origin/main"
script_path="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"

worktree_dir="$CODEX_HOME/worktrees/find-bug/$repo_name/$run_id"
run_dir="$CODEX_HOME/runs/find-bug-pipeline/$repo_name/$run_id"
mkdir -p "$(dirname "$worktree_dir")" "$run_dir"/{schemas,prompts,outputs,logs}

manifest_path="$run_dir/manifest.json"
stage="init"
status="running"
plan_path=""
done_plan_path=""
start_head=""
end_head=""
final_commit=""
error_message=""
script_sha256=""
script_snapshot_path="$run_dir/find-bug-pipeline.sh.snapshot"
runtime_dir="$worktree_dir/.find-bug-runtime"
npm_cache_dir="$runtime_dir/npm-cache"
npm_tmp_dir="$runtime_dir/npm-tmp"
npm_userconfig_path="$runtime_dir/npmrc"
bootstrap_log_path="$run_dir/logs/bootstrap-node.log"

if command -v shasum >/dev/null 2>&1; then
  script_sha256="$(shasum -a 256 "$script_path" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  script_sha256="$(sha256sum "$script_path" | awk '{print $1}')"
else
  script_sha256="unavailable"
fi
cp "$script_path" "$script_snapshot_path"

write_manifest() {
  jq -n \
    --arg schema_version "find-bug-pipeline-v1" \
    --arg run_id "$run_id" \
    --arg repo_root "$repo_root" \
    --arg worktree_dir "$worktree_dir" \
    --arg branch "$branch_name" \
    --arg base_ref "$base_ref" \
    --arg prompt "$user_prompt" \
    --arg stage "$stage" \
    --arg status "$status" \
    --arg plan_path "$plan_path" \
    --arg done_plan_path "$done_plan_path" \
    --arg start_head "$start_head" \
    --arg end_head "$end_head" \
    --arg final_commit "$final_commit" \
    --arg error_message "$error_message" \
    --arg script_path "$script_path" \
    --arg script_sha256 "$script_sha256" \
    --arg script_snapshot_path "$script_snapshot_path" \
    '{
      schema_version: $schema_version,
      run_id: $run_id,
      repo_root: $repo_root,
      worktree_dir: $worktree_dir,
      branch: $branch,
      base_ref: $base_ref,
      prompt: $prompt,
      stage: $stage,
      status: $status,
      plan_path: (if $plan_path == "" then null else $plan_path end),
      done_plan_path: (if $done_plan_path == "" then null else $done_plan_path end),
      start_head: (if $start_head == "" then null else $start_head end),
      end_head: (if $end_head == "" then null else $end_head end),
      final_commit: (if $final_commit == "" then null else $final_commit end),
      error: (if $error_message == "" then null else $error_message end),
      script: {
        path: $script_path,
        sha256: $script_sha256,
        snapshot_path: $script_snapshot_path
      }
    }' > "$manifest_path"
}

on_exit() {
  local exit_code=$?
  if [[ "$status" != "completed" ]]; then
    if [[ -z "$error_message" ]]; then
      error_message="unexpected_exit stage=$stage exit_code=$exit_code"
    fi
    status="failed"
    write_manifest
    echo "pipeline_status=failed" >&2
    echo "error=$error_message" >&2
    echo "run_id=$run_id" >&2
    echo "manifest_path=$manifest_path" >&2
    echo "worktree_dir=$worktree_dir" >&2
  fi
}
trap on_exit EXIT

fail() {
  local message="$1"
  status="failed"
  error_message="$message"
  write_manifest
  echo "error: $message" >&2
  echo "run_id=$run_id" >&2
  echo "manifest_path=$manifest_path" >&2
  echo "worktree_dir=$worktree_dir" >&2
  exit 1
}

bootstrap_worktree_dependencies() {
  if [[ ! -f "$worktree_dir/package.json" ]]; then
    return 0
  fi
  if ! command -v npm >/dev/null 2>&1; then
    fail "repository has package.json but npm is not installed"
  fi

  mkdir -p "$runtime_dir" "$npm_cache_dir" "$npm_tmp_dir"
  : > "$npm_userconfig_path"

  local install_mode="install"
  local -a install_cmd=(npm install --no-audit --no-fund)
  if [[ -f "$worktree_dir/package-lock.json" ]]; then
    install_mode="ci"
    install_cmd=(npm ci --no-audit --no-fund)
  fi

  echo "bootstrap_started=node_deps mode=$install_mode"
  echo "bootstrap_log=$bootstrap_log_path"
  if ! (
    cd "$worktree_dir"
    NPM_CONFIG_CACHE="$npm_cache_dir" \
    NPM_CONFIG_USERCONFIG="$npm_userconfig_path" \
    NPM_CONFIG_TMP="$npm_tmp_dir" \
    npm_config_cache="$npm_cache_dir" \
    npm_config_userconfig="$npm_userconfig_path" \
    npm_config_tmp="$npm_tmp_dir" \
    "${install_cmd[@]}"
  ) >"$bootstrap_log_path" 2>&1; then
    fail "dependency bootstrap failed (see $bootstrap_log_path)"
  fi
  echo "bootstrap_completed=node_deps mode=$install_mode"
}

run_stage() {
  local stage_name="$1"
  local prompt_path="$2"
  local schema_path="$3"
  local output_path="$4"
  local log_path="$5"
  local stage_started_epoch
  local heartbeat_pid=""
  local stage_status
  local -a codex_cmd=(
    codex -a never exec --ephemeral -C "$worktree_dir"
    -s workspace-write
    --add-dir "$SKILLS_ROOT"
    --add-dir "$USEFUL_SKILLS_ROOT"
    --add-dir "$HOME/.npm"
    --output-schema "$schema_path"
    -o "$output_path"
    -c 'shell_environment_policy.include_only=["PATH","HOME","TERM","SSH_AUTH_SOCK","NPM_CONFIG_CACHE","NPM_CONFIG_USERCONFIG","NPM_CONFIG_TMP","npm_config_cache","npm_config_userconfig","npm_config_tmp"]'
    -
  )

  mkdir -p "$(dirname -- "$log_path")"
  : > "$log_path"

  echo "stage_started=$stage_name"
  echo "stage_log=$log_path"

  stage_started_epoch="$(date +%s)"
  if (( HEARTBEAT_SECONDS > 0 )); then
    (
      while true; do
        sleep "$HEARTBEAT_SECONDS"
        if [[ -f "$log_path" ]]; then
          log_bytes="$(wc -c < "$log_path" | tr -d ' ')"
        else
          log_bytes="0"
        fi
        now_epoch="$(date +%s)"
        echo "stage_heartbeat=$stage_name elapsed_sec=$((now_epoch-stage_started_epoch)) log_bytes=$log_bytes"
      done
    ) &
    heartbeat_pid="$!"
  fi

  set +e
  if [[ "$STREAM_LOGS" == "1" ]]; then
    printf '%s\n' "$(<"$prompt_path")" | \
      NPM_CONFIG_CACHE="$npm_cache_dir" \
      NPM_CONFIG_USERCONFIG="$npm_userconfig_path" \
      NPM_CONFIG_TMP="$npm_tmp_dir" \
      npm_config_cache="$npm_cache_dir" \
      npm_config_userconfig="$npm_userconfig_path" \
      npm_config_tmp="$npm_tmp_dir" \
      "${codex_cmd[@]}" 2>&1 | tee -a "$log_path"
    stage_status=$?
  else
    printf '%s\n' "$(<"$prompt_path")" | \
      NPM_CONFIG_CACHE="$npm_cache_dir" \
      NPM_CONFIG_USERCONFIG="$npm_userconfig_path" \
      NPM_CONFIG_TMP="$npm_tmp_dir" \
      npm_config_cache="$npm_cache_dir" \
      npm_config_userconfig="$npm_userconfig_path" \
      npm_config_tmp="$npm_tmp_dir" \
      "${codex_cmd[@]}" >"$log_path" 2>&1
    stage_status=$?
  fi
  set -e

  if [[ -n "$heartbeat_pid" ]]; then
    kill "$heartbeat_pid" 2>/dev/null || true
    wait "$heartbeat_pid" 2>/dev/null || true
  fi

  if [[ "$stage_status" -ne 0 ]]; then
    fail "codex stage failed: $stage_name (see $log_path)"
  fi

  echo "stage_completed=$stage_name"
}

cat > "$run_dir/schemas/stage-find.schema.json" <<'EOF'
{
  "type": "object",
  "required": ["status", "plan_path"],
  "additionalProperties": false,
  "properties": {
    "status": { "type": "string", "enum": ["ok"] },
    "plan_path": { "type": "string", "minLength": 1 }
  }
}
EOF

cat > "$run_dir/schemas/stage-improve.schema.json" <<'EOF'
{
  "type": "object",
  "required": ["status", "plan_path"],
  "additionalProperties": false,
  "properties": {
    "status": { "type": "string", "enum": ["ok"] },
    "plan_path": { "type": "string", "minLength": 1 }
  }
}
EOF

cat > "$run_dir/schemas/stage-implement.schema.json" <<'EOF'
{
  "type": "object",
  "required": ["status", "done_plan_path", "commit_sha"],
  "additionalProperties": false,
  "properties": {
    "status": { "type": "string", "enum": ["ok"] },
    "done_plan_path": { "type": "string", "minLength": 1 },
    "commit_sha": { "type": "string", "pattern": "^[0-9a-f]{7,40}$" }
  }
}
EOF

echo "run_id=$run_id"
echo "repo_root=$repo_root"
echo "base_ref=$base_ref"
echo "branch=$branch_name"
echo "worktree_dir=$worktree_dir"
echo "logs_dir=$run_dir/logs"
echo "manifest_path=$manifest_path"

if ! git -C "$repo_root" fetch origin main --prune >"$run_dir/logs/git-fetch.log" 2>&1; then
  fail "git fetch origin main failed (see $run_dir/logs/git-fetch.log)"
fi

if ! git -C "$repo_root" worktree add -b "$branch_name" "$worktree_dir" "$base_ref" >"$run_dir/logs/git-worktree-add.log" 2>&1; then
  fail "git worktree add failed (see $run_dir/logs/git-worktree-add.log)"
fi

if ! start_head="$(git -C "$worktree_dir" rev-parse HEAD 2>/dev/null)"; then
  fail "unable to resolve start HEAD in new worktree"
fi
mkdir -p "$runtime_dir" "$HOME/.npm"
bootstrap_worktree_dependencies
write_manifest

stage="find"
write_manifest
cat > "$run_dir/prompts/stage-find.prompt.txt" <<EOF
Use this skill: [\$find-bug-generic]($skill_find)

Bug-hunt request:
$user_prompt

Requirements for this stage:
- Follow the skill exactly.
- Write exactly one ExecPlan to .agent/potential-bugs in the current working tree.
- Do not implement any fix in this stage.
- Return only JSON matching the schema.
EOF

run_stage \
  "find" \
  "$run_dir/prompts/stage-find.prompt.txt" \
  "$run_dir/schemas/stage-find.schema.json" \
  "$run_dir/outputs/stage-find.output.json" \
  "$run_dir/logs/stage-find.log"

plan_path="$(jq -r '.plan_path' "$run_dir/outputs/stage-find.output.json")"
plan_path="$(resolve_path_in_worktree "$plan_path" "$worktree_dir")"
if [[ ! -f "$plan_path" ]]; then
  fail "stage find returned plan_path that does not exist: $plan_path"
fi
if [[ "$plan_path" != "$worktree_dir/"* ]]; then
  fail "stage find returned plan outside worktree: $plan_path"
fi
write_manifest

stage="improve1"
write_manifest
cat > "$run_dir/prompts/stage-improve1.prompt.txt" <<EOF
Use this skill: [\$execplan-improve]($skill_improve)

Improve this exact ExecPlan in-place:
$plan_path

Requirements:
- Run one improvement pass only.
- Keep the same plan intent.
- Return only JSON matching the schema:
{"status":"ok","plan_path":"$plan_path"}
EOF

run_stage \
  "improve1" \
  "$run_dir/prompts/stage-improve1.prompt.txt" \
  "$run_dir/schemas/stage-improve.schema.json" \
  "$run_dir/outputs/stage-improve1.output.json" \
  "$run_dir/logs/stage-improve1.log"

plan_path="$(jq -r '.plan_path' "$run_dir/outputs/stage-improve1.output.json")"
plan_path="$(resolve_path_in_worktree "$plan_path" "$worktree_dir")"
if [[ ! -f "$plan_path" ]]; then
  fail "stage improve1 returned plan_path that does not exist: $plan_path"
fi
write_manifest

stage="improve2"
write_manifest
cat > "$run_dir/prompts/stage-improve2.prompt.txt" <<EOF
Use this skill: [\$execplan-improve]($skill_improve)

Improve this exact ExecPlan in-place:
$plan_path

Requirements:
- Run one improvement pass only.
- Keep the same plan intent.
- Return only JSON matching the schema:
{"status":"ok","plan_path":"$plan_path"}
EOF

run_stage \
  "improve2" \
  "$run_dir/prompts/stage-improve2.prompt.txt" \
  "$run_dir/schemas/stage-improve.schema.json" \
  "$run_dir/outputs/stage-improve2.output.json" \
  "$run_dir/logs/stage-improve2.log"

plan_path="$(jq -r '.plan_path' "$run_dir/outputs/stage-improve2.output.json")"
plan_path="$(resolve_path_in_worktree "$plan_path" "$worktree_dir")"
if [[ ! -f "$plan_path" ]]; then
  fail "stage improve2 returned plan_path that does not exist: $plan_path"
fi
write_manifest

stage="implement"
write_manifest
cat > "$run_dir/prompts/stage-implement.prompt.txt" <<EOF
Use this skill: [\$implement-execplan]($skill_implement)

Implement this exact ExecPlan:
$plan_path

Hard requirements:
- Implement the plan completely.
- Commit the implementation.
- Move/rename the finished plan to .agent/done/<name>-implemented-YYYYMMDD.md.
- Return only JSON matching the schema:
{"status":"ok","done_plan_path":"<absolute-or-repo-relative-path>","commit_sha":"<new-head-commit-sha>"}
EOF

run_stage \
  "implement" \
  "$run_dir/prompts/stage-implement.prompt.txt" \
  "$run_dir/schemas/stage-implement.schema.json" \
  "$run_dir/outputs/stage-implement.output.json" \
  "$run_dir/logs/stage-implement.log"

done_plan_path="$(jq -r '.done_plan_path' "$run_dir/outputs/stage-implement.output.json")"
done_plan_path="$(resolve_path_in_worktree "$done_plan_path" "$worktree_dir")"
final_commit="$(jq -r '.commit_sha' "$run_dir/outputs/stage-implement.output.json")"

if [[ ! -f "$done_plan_path" ]]; then
  fail "stage implement returned done_plan_path that does not exist: $done_plan_path"
fi
if ! git -C "$worktree_dir" rev-parse --verify "${final_commit}^{commit}" >/dev/null 2>&1; then
  fail "stage implement returned commit that does not exist: $final_commit"
fi
if ! end_head="$(git -C "$worktree_dir" rev-parse HEAD 2>/dev/null)"; then
  fail "unable to resolve end HEAD after implement stage"
fi
if [[ "$start_head" == "$end_head" ]]; then
  fail "implement stage did not create a new commit"
fi
if [[ "$end_head" != "$final_commit" ]]; then
  fail "implement stage commit_sha ($final_commit) is not worktree HEAD ($end_head)"
fi
if [[ -n "$(git -C "$worktree_dir" status --porcelain)" ]]; then
  fail "worktree is not clean after implement stage"
fi

stage="done"
status="completed"
write_manifest

echo "status=completed"
echo "run_id=$run_id"
echo "worktree_dir=$worktree_dir"
echo "branch=$branch_name"
echo "plan_path=$plan_path"
echo "done_plan_path=$done_plan_path"
echo "final_commit=$final_commit"
echo "manifest_path=$manifest_path"
