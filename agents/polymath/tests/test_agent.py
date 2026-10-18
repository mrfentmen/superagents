"""Tests for the polymath: routing, ranking, federation, and the brief merge.

    python3 agents/polymath/tests/test_agent.py

The federation tests run against a real sibling ACP agent process (a tiny offline responder
built in this file), so the child supervision executes exactly as it does when he spawns the
answerer repo's agents. No network anywhere.
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
import federation as fed  # noqa: E402

FAKE_SIBLING = r"""
import sys, json
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()
def recv():
    return json.loads(sys.stdin.readline())
req = recv()  # initialize
send({"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":1,"agentCapabilities":{},
      "authMethods":[],"agentInfo":{"name":"fake-sibling","title":"Fake","version":"1.0.0"}}})
while True:
    try:
        req = recv()
    except Exception:
        break
    method = req.get("method", "")
    if method == "session/new":
        send({"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"fake-session","modes":[]}})
    elif method == "session/prompt":
        text = "".join(b.get("text","") for b in req.get("params",{}).get("prompt",[]))
        send({"jsonrpc":"2.0","method":"session/update","params":{"update":{
            "sessionUpdate":"agent_message_chunk","content":{"type":"text",
            "text":"FAKE ANSWER for %r\nsecond line\n" % text}}}})
        send({"jsonrpc":"2.0","id":req["id"],"result":{"stopReason":"end-turn"}})
    elif method in ("session/cancel", "session/load"):
        continue
    else:
        send({"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"unhandled"}})
"""


class RouteTests(unittest.TestCase):
    def test_brief_with_place(self):
        skill, params = agent.route("brief me on Denver")
        self.assertEqual((skill, params["place"]), ("brief", "Denver"))
        self.assertEqual(params["topics"], [])

    def test_brief_with_named_topics(self):
        skill, params = agent.route("brief me for air and moon in Denver")
        self.assertEqual(skill, "brief")
        self.assertEqual(params["place"], "Denver")
        self.assertEqual(sorted(params["topics"]), ["air", "moon"])

    def test_ask_pair(self):
        self.assertEqual(agent.route("ask moon: when is the next full moon?"),
                         ("ask", {"agent": "moon", "question": "when is the next full moon?"}))

    def test_unknown_ask_abstains_to_help(self):
        self.assertEqual(agent.route("ask nothere: hi")[0], "help")

    def test_catalog_and_find_and_help(self):
        self.assertEqual(agent.route("what siblings do you have?")[0], "catalog")
        self.assertEqual(agent.route("who should answer: is the beach safe?")[0], "find")
        self.assertEqual(agent.route("what can you do")[0], "help")

    def test_watch_words_hire_the_sentry(self):
        skill, params = agent.route("watch air quality in Denver over 150")
        self.assertEqual((skill, list(params)), ("hire", ["order"]))

    def test_unformed_question_routes_to_top_ranked(self):
        skill, params = agent.route("is the beach water safe in Boston today?")
        self.assertEqual(skill, "ask")
        self.assertEqual(params["agent"], "tides")

    def test_unroutable_falls_back_to_help(self):
        self.assertEqual(agent.route("tell me a joke")[0], "help")


class RankingTests(unittest.TestCase):
    def test_beach_safety_points_to_tides(self):
        top = fed.find_ranking("is the beach safe in Boston?")[0]
        self.assertEqual(top["agent"], "tides")
        self.assertIn("beach", top["hits"])

    def test_quake_words_point_to_hazards(self):
        top = fed.find_ranking("was there an earthquake near Tokyo just now?")[0]
        self.assertEqual(top["agent"], "hazards")

    def test_real_air_words(self):
        top = fed.find_ranking("how bad is the smog in Delhi right now?")[0]
        self.assertEqual(top["agent"], "air")

    def test_no_hits_no_ranking(self):
        self.assertEqual(fed.find_ranking("tell me a joke"), [])


class PlaceAndSiblingTests(unittest.TestCase):
    def test_place_of_prepositions(self):
        self.assertEqual(fed.place_of("how is it in Buenos Aires please?"), "Buenos Aires")
        self.assertIsNone(fed.place_of("brief me on the thing"))

    def test_sibling_question_uses_template_for_bare_place(self):
        row = fed.siblings()["air"]
        self.assertEqual(fed.sibling_question(row, "Denver"),
                         "how is the air quality in Denver right now?")

    def test_sibling_question_verbatim_for_formed(self):
        row = fed.siblings()["moon"]
        self.assertEqual(fed.sibling_question(row, "what is the next full moon?"),
                         "what is the next full moon?")


class MergeTests(unittest.TestCase):
    def test_brief_names_the_silent_sibling(self):
        air = fed.SiblingTurn("air")
        air.ok = True
        air.text = "US AQI 44 - Good\ngrid row\nanother\nmore\nmore2\nmore3\ntail"


        moon = fed.SiblingTurn("moon")
        moon.error = "nothing was answered"
        body, summary = agent.render_brief("Denver", [air, moon])
        self.assertIn("1 of 2", body)
        self.assertIn("[air]", body)
        self.assertIn("+3 more line(s)", body)
        self.assertIn("[moon] not answered: nothing was answered", body)
        self.assertEqual(summary, "1/2 sibling answers")


class FederationChildTests(unittest.TestCase):
    """Real child processes over stdio, pointed at the offline responder."""

    def _with_fake(self, tmp: str):
        old = os.environ.get("POLYMATH_FAKE_SIBLING")
        os.environ["POLYMATH_FAKE_SIBLING"] = str(Path(tmp) / "fake_sibling.py")
        (Path(tmp) / "fake_sibling.py").write_text(FAKE_SIBLING)
        return old

    def _without_fake(self, old):
        if old is None:
            os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        else:
            os.environ["POLYMATH_FAKE_SIBLING"] = old

    def test_real_child_spawn_and_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self._with_fake(tmp)
            try:
                turn = fed.run_sibling("air", "Denver")
            finally:
                self._without_fake(old)
            self.assertTrue(turn.ok, turn.error)
            self.assertIn("FAKE ANSWER for 'how is the air quality in Denver right now?'",
                          turn.text)
            self.assertEqual(turn.stop_reason, "end-turn")

    def test_fan_out_collects_named_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self._with_fake(tmp)
            try:
                rows = fed.fan_out({"air": "Denver", "moon": "Lisbon"}, timeout=30)
            finally:
                self._without_fake(old)
            self.assertEqual([row.agent for row in rows], ["air", "moon"])
            self.assertTrue(all(row.ok for row in rows), [row.error for row in rows])

    def test_unconfigured_home_is_an_honest_row_not_a_crash(self):
        old = os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        home = os.environ.pop("AWESOME_SERVERS_HOME", None)
        try:
            turn = fed.run_sibling("air", "Denver")
        finally:
            if old is not None:
                os.environ["POLYMATH_FAKE_SIBLING"] = old
            if home is not None:
                os.environ["AWESOME_SERVERS_HOME"] = home
        self.assertFalse(turn.ok)
        self.assertIn("AWESOME_SERVERS_HOME", turn.error)

    def test_hire_spawns_the_real_sentry(self):
        # the watch handoff goes to the actual in-repo sentry, no fallback fakes
        old = os.environ.get("POLYMATH_FAKE_SIBLING")
        os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        try:
            sentry = fed.run_sibling(fed.watch_handler(), "list my watches", timeout=60)
        finally:
            if old is not None:
                os.environ["POLYMATH_FAKE_SIBLING"] = old
        self.assertTrue(sentry.ok, sentry.error or "sentry did not answer")
        self.assertIn("No watches installed yet", sentry.text)


if __name__ == "__main__":
    unittest.main()
