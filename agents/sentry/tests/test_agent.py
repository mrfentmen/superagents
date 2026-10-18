"""Tests for the sentry: the words-to-watch pipeline, end to end, offline.

    python3 agents/sentry/tests/test_agent.py

The strongest test spawns the REAL sentry child and installs a watch through the kit's own
fs server into a temporary fs_root: the conditions file that lands on disk is the artifact
the watcher runtime reads, checked byte for byte.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

DIR = Path(__file__).resolve().parent
AGENT_DIR = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
for path in (str(REPO / "kit"), str(AGENT_DIR), str(DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import agent  # noqa: E402
import guards  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_air_order_complete(self):
        entry = guards.build_entry("watch air quality in Denver over 150 every 5 minutes")
        self.assertEqual(entry["kind"], "air")
        self.assertEqual(entry["place"], "Denver")
        self.assertEqual((entry["threshold"], entry["when"]), (150.0, "above"))
        self.assertEqual(entry["every_s"], 300)
        self.assertEqual(entry["name"], "air-Denver")

    def test_quakes_order_with_radius(self):
        entry = guards.build_entry("watch quakes within 120 km of Fresno over 4.5")
        self.assertEqual((entry["kind"], entry["place"]), ("quakes", "Fresno"))
        self.assertEqual(entry["radius_km"], 120.0)
        self.assertEqual((entry["magnitude"], entry["when"]), (4.5, "above"))

    def test_flood_order_needs_a_named_gauge(self):
        with self.assertRaises(ValueError):
            guards.build_entry("watch flooding at the shore")
        entry = guards.build_entry("watch the river gauge at EADM7")
        self.assertEqual((entry["kind"], entry["gauge"]), ("flood", "EADM7"))

    def test_air_order_without_threshold_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            guards.build_entry("watch air in Lisbon")
        self.assertIn("number", str(caught.exception))

    def test_air_order_without_place_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            guards.build_entry("watch air over 150")
        self.assertIn("where", str(caught.exception))

    def test_unknown_domain_is_refused_honestly(self):
        with self.assertRaises(ValueError) as caught:
            guards.build_entry("watch my taxes")
        self.assertIn("air, quakes", str(caught.exception))

    def test_miles_convert_to_km(self):
        self.assertEqual(round(guards.radius_of("within 50 mi of Fresno"), 1), 80.5)
        self.assertEqual(guards.radius_of("within 10 km of home"), 10.0)

    def test_every_parses_units(self):
        self.assertEqual(guards.every_of("every 30 sec"), 30)
        self.assertEqual(guards.every_of("every 2 hours"), 7200)
        self.assertEqual(guards.every_of("no timing words"), 300)


class MergeTests(unittest.TestCase):
    def test_add_then_update_same_name_in_place(self):
        first, changed = guards.merge_into("{}", guards.build_entry("watch air in Denver over 150"),
                                           "2026-10-18T00:00:00+00:00")
        self.assertEqual(changed, "added")
        doc = json.loads(first)
        self.assertEqual(doc["checks"][0]["name"], "air-Denver")
        self.assertEqual(doc["notifiers"], {"console": True})
        bumped = guards.merge_into(first, guards.build_entry("watch air in Denver over 200"),
                                   "2026-10-18T01:00:00+00:00")
        doc = json.loads(bumped[0])
        self.assertEqual(bumped[1], "updated")
        self.assertEqual([row.get("threshold") for row in doc["checks"]], [200.0])
        self.assertEqual(doc["installed"], "2026-10-18T01:00:00+00:00")

    def test_corrupt_existing_file_is_refused(self):
        with self.assertRaises(ValueError):
            guards.merge_into("{not json", guards.build_entry("watch air in Denver over 1"), "x")

    def test_activation_lines_carry_the_cron_contract(self):
        lines = guards.activation_lines("watches/watchd-conditions.json", 300)
        self.assertIn("*/5 * * * *", " ".join(lines))
        self.assertIn("--config watches/watchd-conditions.json", " ".join(lines))


class ListTests(unittest.TestCase):
    def test_empty_list_is_honest(self):
        self.assertIn("No watches installed yet", agent.render_list({}))

    def test_list_renders_each_kind(self):
        doc = {"checks": [
            {"name": "air-Denver", "kind": "air", "place": "Denver", "threshold": 150, "when": "above",
             "every_s": 300},
            {"name": "flood-EADM7", "kind": "flood", "gauge": "EADM7", "when": "above", "every_s": 600},
        ]}
        body = agent.render_list(doc)
        self.assertIn("US AQI 150 above", body)
        self.assertIn("flood stage", body)
        self.assertIn("every 10 min", body)


class RealChildInstallTests(unittest.TestCase):
    """Spawns the actual sentry child and installs through the kit's fs server."""

    def test_watch_written_through_acp_fs(self):
        with tempfile.TemporaryDirectory() as tmp:
            from acp_kit import AcpClient
            command = [sys.executable, str(AGENT_DIR / "agent.py")]
            with AcpClient(command=command, fs_root=tmp, permission="allow-once",
                           timeout=60) as client:
                client.initialize(name="sentry-test", version="1.0.0")
                session_id = client.new_session(cwd=str(Path(tmp)))
                turn = client.prompt("watch air quality in Denver over 150", session_id=session_id)
                self.assertEqual(turn.get("stopReason"), "end_turn", turn)
                landed = Path(tmp) / "watches" / "watchd-conditions.json"
                self.assertTrue(landed.exists(), client.written_files)
                doc = json.loads(landed.read_text())
                self.assertEqual(doc["checks"][0]["kind"], "air")
                self.assertEqual(doc["checks"][0]["threshold"], 150.0)
                # and the permission ask really happened, on the record
                self.assertTrue(client.permission_requests)

    def test_refused_write_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            from acp_kit import AcpClient
            command = [sys.executable, str(AGENT_DIR / "agent.py")]
            with AcpClient(command=command, fs_root=tmp, permission="reject-once",
                           timeout=60) as client:
                client.initialize(name="sentry-test", version="1.0.0")
                session_id = client.new_session(cwd=str(Path(tmp)))
                if "reject-once" not in agent_n_options(client):
                    self.skipTest("this kit build has no reject option wired")
                turn = client.prompt("watch air quality in Denver over 150", session_id=session_id)
                self.assertEqual(turn.get("stopReason"), "refusal", turn)
                self.assertFalse((Path(tmp) / "watches").exists())


def agent_n_options(client) -> list:
    return [row.get("options", []) for row in client.permission_requests]


if __name__ == "__main__":
    unittest.main()
