import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path("/Users/georgepickett/useful-codex-skills/tool-error-analyzer/scripts/repo_tool_error_digest.py")
)
SPEC = importlib.util.spec_from_file_location("repo_tool_error_digest", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


THREADS_SCHEMA = """
create table threads (
    id text primary key,
    rollout_path text not null,
    created_at integer not null,
    updated_at integer not null,
    source text not null,
    model_provider text not null,
    cwd text not null,
    title text not null,
    sandbox_policy text not null,
    approval_mode text not null,
    tokens_used integer not null default 0,
    has_user_event integer not null default 0,
    archived integer not null default 0,
    archived_at integer,
    git_sha text,
    git_branch text,
    git_origin_url text,
    cli_version text not null default '',
    first_user_message text not null default '',
    agent_nickname text,
    agent_role text,
    memory_mode text not null default 'enabled',
    model text,
    reasoning_effort text,
    agent_path text
)
"""


def make_exec_pair(call_id: str, ts: str, cmd: str, output: str) -> list[str]:
    return [
        json.dumps(
            {
                "timestamp": ts,
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": cmd}),
                    "call_id": call_id,
                },
            }
        ),
        json.dumps(
            {
                "timestamp": ts,
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }
        ),
    ]


def make_patch_pair(call_id: str, ts: str, patch: str, output: str) -> list[str]:
    return [
        json.dumps(
            {
                "timestamp": ts,
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "status": "completed",
                    "call_id": call_id,
                    "name": "apply_patch",
                    "input": patch,
                },
            }
        ),
        json.dumps(
            {
                "timestamp": ts,
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }
        ),
    ]


class RepoToolErrorDigestTests(unittest.TestCase):
    def test_rg_no_match_is_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript = Path(tmpdir) / "rollout.jsonl"
            transcript.write_text(
                "\n".join(
                    make_exec_pair(
                        "call-1",
                        "2026-04-01T22:00:00Z",
                        'rg -n "missing"',
                        "\n".join(
                            [
                                "Command: /opt/homebrew/bin/zsh -lc 'rg -n \"missing\"'",
                                "Chunk ID: abc",
                                "Wall time: 0.0 seconds",
                                "Process exited with code 1",
                                "Original token count: 1",
                                "Output:",
                            ]
                        ),
                    )
                )
                + "\n"
            )
            events = MODULE.parse_tool_events(str(transcript), "thread-1")
            self.assertEqual(len(events), 1)
            self.assertFalse(events[0].meaningful_failure)

    def test_shell_globbing_failure_classifies_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript = Path(tmpdir) / "rollout.jsonl"
            transcript.write_text(
                "\n".join(
                    make_exec_pair(
                        "call-1",
                        "2026-04-01T22:00:00Z",
                        "sed -n '1,200p' app/api/projects/[projectId]/route.ts",
                        "\n".join(
                            [
                                "Command: /opt/homebrew/bin/zsh -lc \"sed -n '1,200p' app/api/projects/[projectId]/route.ts\"",
                                "Chunk ID: abc",
                                "Wall time: 0.0 seconds",
                                "Process exited with code 1",
                                "Original token count: 1",
                                "Output:",
                                "zsh:1: no matches found: app/api/projects/[projectId]/route.ts",
                            ]
                        ),
                    )
                    + make_exec_pair(
                        "call-2",
                        "2026-04-01T22:00:05Z",
                        'sed -n \'1,200p\' "app/api/projects/[projectId]/route.ts"',
                        "\n".join(
                            [
                                "Command: /opt/homebrew/bin/zsh -lc \"sed -n '1,200p' \\\"app/api/projects/[projectId]/route.ts\\\"\"",
                                "Chunk ID: def",
                                "Wall time: 0.0 seconds",
                                "Process exited with code 0",
                                "Original token count: 5",
                                "Output:",
                                "export async function DELETE() {}",
                            ]
                        ),
                    )
                )
                + "\n"
            )
            events = MODULE.parse_tool_events(str(transcript), "thread-1")
            MODULE.detect_recoveries(events)
            failures = [event for event in events if event.meaningful_failure]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].error_kind, "shell_globbing")
            self.assertTrue(failures[0].recovered_later)

    def test_apply_patch_failure_classifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript = Path(tmpdir) / "rollout.jsonl"
            transcript.write_text(
                "\n".join(
                    make_patch_pair(
                        "call-1",
                        "2026-04-01T22:00:00Z",
                        "*** Begin Patch\n*** Update File: /tmp/server_test.go\n@@\n-old\n+new\n*** End Patch\n",
                        "apply_patch verification failed: Failed to find expected lines in /tmp/server_test.go:\n-old",
                    )
                )
                + "\n"
            )
            events = MODULE.parse_tool_events(str(transcript), "thread-1")
            failures = [event for event in events if event.meaningful_failure]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].error_kind, "patch_verification_failed")
            self.assertIn("server_test.go", failures[0].target_hints)

    def test_build_payload_includes_repo_scoped_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            sessions_dir = home / "sessions" / "2026" / "04" / "01"
            sessions_dir.mkdir(parents=True)
            transcript = sessions_dir / "rollout-thread.jsonl"
            transcript.write_text(
                "\n".join(
                    make_exec_pair(
                        "call-1",
                        "2026-04-01T22:00:00Z",
                        "git -C /Users/georgepickett/taskrally status --short",
                        "\n".join(
                            [
                                "Command: /opt/homebrew/bin/zsh -lc 'git -C /Users/georgepickett/taskrally status --short'",
                                "Chunk ID: abc",
                                "Wall time: 0.0 seconds",
                                "Process exited with code 128",
                                "Original token count: 1",
                                "Output:",
                                "fatal: not a git repository (or any of the parent directories): .git",
                            ]
                        ),
                    )
                    + make_patch_pair(
                        "call-2",
                        "2026-04-01T22:01:00Z",
                        "*** Begin Patch\n*** Update File: /Users/georgepickett/taskrally/server_test.go\n@@\n-old\n+new\n*** End Patch\n",
                        "apply_patch verification failed: Failed to find expected lines in /Users/georgepickett/taskrally/server_test.go:\n-old",
                    )
                )
                + "\n"
            )

            state_db = home / "state_5.sqlite"
            with sqlite3.connect(str(state_db)) as conn:
                conn.executescript(THREADS_SCHEMA)
                conn.execute(
                    """
                    insert into threads (
                        id, rollout_path, created_at, updated_at, source, model_provider, cwd,
                        title, sandbox_policy, approval_mode, first_user_message
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "thread-1",
                        str(transcript),
                        int(MODULE.SESSION_ANALYZER.datetime(2026, 4, 1, 21, 55, tzinfo=MODULE.SESSION_ANALYZER.timezone.utc).timestamp()),
                        int(MODULE.SESSION_ANALYZER.datetime(2026, 4, 1, 22, 2, tzinfo=MODULE.SESSION_ANALYZER.timezone.utc).timestamp()),
                        "",
                        "codex",
                        "/Users/georgepickett/taskrally",
                        "Thread 1",
                        "danger-full-access",
                        "never",
                        "inspect tool failures",
                    ),
                )
                conn.commit()

            previous_home = os.environ.get("CODEX_HOME")
            os.environ["CODEX_HOME"] = str(home)
            try:
                args = MODULE.argparse.Namespace(
                    repo="~/taskrally",
                    when=None,
                    date="2026-04-01",
                    last_hours=None,
                    timezone="America/Los_Angeles",
                    format="json",
                    include_subagents=False,
                    allow_basename_fallback=False,
                    allow_incomplete=False,
                )
                payload = MODULE.build_payload(args)
            finally:
                if previous_home is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = previous_home

            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["totals"]["tool_error_count"], 2)
            self.assertEqual(payload["error_clusters"][0]["cluster_key"], "patch_verification_failed")
            self.assertEqual(payload["candidate_improvements"][0]["cluster_key"], "patch_verification_failed")


if __name__ == "__main__":
    unittest.main()
