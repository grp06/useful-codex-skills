import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path("/Users/georgepickett/.codex/skills/analyzing-codex-sessions/scripts/repo_session_digest.py")
)
SPEC = importlib.util.spec_from_file_location("repo_session_digest", SCRIPT_PATH)
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

LOGS_SCHEMA = """
create table logs (
    id integer primary key autoincrement,
    ts integer not null,
    ts_nanos integer not null,
    level text not null,
    target text not null,
    feedback_log_body text,
    module_path text,
    file text,
    line integer,
    thread_id text,
    process_uuid text,
    estimated_bytes integer not null default 0
)
"""


class RepoSessionDigestTests(unittest.TestCase):
    def test_resolve_time_window_supports_last_hours(self) -> None:
        args = MODULE.argparse.Namespace(
            repo="~/TaskRally",
            when=None,
            date=None,
            last_hours=6,
            timezone="America/Los_Angeles",
            format="markdown",
            include_git=False,
            include_subagents=False,
            allow_basename_fallback=False,
            index_path=None,
            allow_incomplete=False,
        )

        window = MODULE.resolve_time_window(args)
        self.assertEqual(window.mode, "rolling_hours")
        self.assertEqual(window.last_hours, 6)
        self.assertEqual(window.label, "last 6 hours")
        self.assertIsNone(window.target_date)
        self.assertEqual(window.end_ts - window.start_ts, 6 * 60 * 60)

    def test_classify_cwd_requires_flag_for_basename_fallback(self) -> None:
        repo_canon = "/users/georgepickett/taskrally"
        repo_name = "taskrally"

        self.assertIsNotNone(
            MODULE.classify_cwd(
                "/Users/georgepickett/taskrally",
                repo_canon,
                repo_name,
                allow_basename_fallback=False,
            )
        )
        self.assertIsNone(
            MODULE.classify_cwd(
                "/tmp/taskrally",
                repo_canon,
                repo_name,
                allow_basename_fallback=False,
            )
        )
        fallback = MODULE.classify_cwd(
            "/tmp/taskrally",
            repo_canon,
            repo_name,
            allow_basename_fallback=True,
        )
        self.assertEqual(fallback.reason, "cwd_basename_match")
        self.assertEqual(fallback.confidence, "low")

    def test_inventory_includes_previous_day_thread_with_target_day_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            sessions_dir = home / "sessions" / "2026" / "03" / "31"
            sessions_dir.mkdir(parents=True)
            transcript = sessions_dir / "rollout-older-thread.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-31T18:34:46.545Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "investigate release gate"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-31T18:35:10.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "Still looking into it."}],
                                },
                            }
                        ),
                    ]
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
                        int(MODULE.datetime(2026, 3, 30, 23, 0, tzinfo=MODULE.timezone.utc).timestamp()),
                        int(MODULE.datetime(2026, 4, 1, 1, 0, tzinfo=MODULE.timezone.utc).timestamp()),
                        "",
                        "codex",
                        "/Users/georgepickett/TaskRally",
                        "Thread 1",
                        "danger-full-access",
                        "never",
                        "investigate release gate",
                    ),
                )
                conn.commit()

            window = MODULE.TimeWindow(
                mode="calendar_day",
                label="2026-03-31",
                start_utc=MODULE.datetime(2026, 3, 31, 7, 0, tzinfo=MODULE.timezone.utc),
                end_utc=MODULE.datetime(2026, 4, 1, 7, 0, tzinfo=MODULE.timezone.utc),
                start_ts=int(MODULE.datetime(2026, 3, 31, 7, 0, tzinfo=MODULE.timezone.utc).timestamp()),
                end_ts=int(MODULE.datetime(2026, 4, 1, 7, 0, tzinfo=MODULE.timezone.utc).timestamp()),
                timezone="America/Los_Angeles",
                target_date="2026-03-31",
                last_hours=None,
            )

            inventory = MODULE.inventory_sessions_from_state(
                home=home,
                window=window,
                repo_canon="/users/georgepickett/taskrally",
                repo_name="taskrally",
                include_subagents=False,
                allow_basename_fallback=False,
            )

            self.assertEqual(len(inventory), 1)
            self.assertIn("transcript_activity_on_day", inventory[0].inventory_reasons)
            self.assertEqual(inventory[0].match_confidence, "high")

    def test_classify_session_outcome_detects_plan_only_and_merge(self) -> None:
        plan = MODULE.classify_session_outcome(
            [{"text": "make a plan. just think out loud, dont make changes yet"}],
            "Here's the plan.",
        )
        self.assertEqual(plan["status"], "plan_only")

        merged = MODULE.classify_session_outcome(
            [{"text": "commit and push"}],
            "PR opened and merged: https://example.com/pr/1",
        )
        self.assertEqual(merged["status"], "implemented_and_merged")

    def test_candidate_next_actions_prioritize_release_blockers(self) -> None:
        sessions = [
            {
                "session_id": "s1",
                "filename": "a.jsonl",
                "started_at": "2026-03-31T10:00:00Z",
                "started_at_local": "2026-03-31T03:00:00-07:00",
                "assistant_tail": "Still investigating release gate failure.",
                "match_confidence": "high",
                "low_signal_operational": False,
                "priority_signals": [],
                "user_messages": [{"text": "find the root cause of the release rollout failure"}],
                "outcome": {
                    "status": "investigation_only",
                    "confidence": "medium",
                    "evidence": ["thread emphasizes investigation/root-cause analysis without landing work"],
                },
            },
            {
                "session_id": "s2",
                "filename": "b.jsonl",
                "started_at": "2026-03-31T11:00:00Z",
                "started_at_local": "2026-03-31T04:00:00-07:00",
                "assistant_tail": "Here is the PostHog plan.",
                "match_confidence": "high",
                "low_signal_operational": False,
                "priority_signals": [],
                "user_messages": [{"text": "make a plan for self-hosted posthog"}],
                "outcome": {
                    "status": "plan_only",
                    "confidence": "high",
                    "evidence": ["latest user request explicitly asked for planning without changes"],
                },
            },
        ]

        for session in sessions:
            theme_key, theme_title = MODULE.theme_for_session(session)
            session["theme"] = {"key": theme_key, "title": theme_title}

        summaries = MODULE.build_theme_summaries(sessions, "America/Los_Angeles")
        candidates = MODULE.build_candidate_next_actions(summaries)
        self.assertEqual(candidates[0]["theme_key"], "release_rollout")
        self.assertGreater(candidates[0]["score"], candidates[1]["score"])

    def test_theme_summary_marks_landed_but_still_unverified_work(self) -> None:
        sessions = [
            {
                "session_id": "s1",
                "filename": "a.jsonl",
                "started_at": "2026-03-31T10:00:00Z",
                "started_at_local": "2026-03-31T03:00:00-07:00",
                "assistant_tail": "Pushed successfully to origin/main.",
                "match_confidence": "high",
                "low_signal_operational": False,
                "priority_signals": [],
                "user_messages": [{"text": "fix the release gate and push"}],
                "outcome": {
                    "status": "implemented_and_pushed",
                    "confidence": "high",
                    "evidence": ["assistant tail contains push markers"],
                },
            },
            {
                "session_id": "s2",
                "filename": "b.jsonl",
                "started_at": "2026-03-31T12:00:00Z",
                "started_at_local": "2026-03-31T05:00:00-07:00",
                "assistant_tail": "Still investigating the loader_runtime failure.",
                "match_confidence": "high",
                "low_signal_operational": False,
                "priority_signals": [],
                "user_messages": [{"text": "did it succeed? whats next?"}],
                "outcome": {
                    "status": "investigation_only",
                    "confidence": "medium",
                    "evidence": ["thread emphasizes investigation/root-cause analysis without landing work"],
                },
            },
        ]
        for session in sessions:
            theme_key, theme_title = MODULE.theme_for_session(session)
            session["theme"] = {"key": theme_key, "title": theme_title}

        summaries = MODULE.build_theme_summaries(sessions, "America/Los_Angeles")
        release = next(item for item in summaries if item["theme_key"] == "release_rollout")
        self.assertEqual(release["current_state"], "implemented_but_unverified")

    def test_low_signal_operational_threads_do_not_become_candidates(self) -> None:
        session = {
            "session_id": "s1",
            "filename": "a.jsonl",
            "started_at": "2026-03-31T10:00:00Z",
            "started_at_local": "2026-03-31T03:00:00-07:00",
            "assistant_tail": "Already up to date.",
            "match_confidence": "high",
            "low_signal_operational": False,
            "priority_signals": [],
            "user_messages": [{"text": "pull the latest changes"}],
            "outcome": {
                "status": "unknown",
                "confidence": "low",
                "evidence": ["no strong completion or blockage marker found"],
            },
        }
        theme_key, theme_title = MODULE.theme_for_session(session)
        session["theme"] = {"key": theme_key, "title": theme_title}

        summaries = MODULE.build_theme_summaries([session], "America/Los_Angeles")
        self.assertTrue(summaries[0]["low_signal_operational"])
        candidates = MODULE.build_candidate_next_actions(summaries)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
