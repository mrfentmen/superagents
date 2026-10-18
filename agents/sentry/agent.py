"""The sentry: your words become a watch the watcher runtime obeys.

This is the words-to-watch loop as a working agent, not a slogan:

    you:  watch air quality in Denver over 150 every 5 minutes
    me:   -> a watch entry (kind air, place Denver, threshold 150)
          -> one fs/write_text_file behind session/request_permission writing the merged
             conditions file watches/<file>.json
          -> the exact activation lines for the watcher runtime

I write conditions; the watcher (watchd, in the sibling repo) obeys them. The file is the
whole contract - no private channel. A feed that will not answer is logged by the watcher
as a feed problem, never as a fire; that invariant stays true because I do not run the
picket myself.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for path in (str(REPO / "kit"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from acp_kit import STOP_END_TURN, STOP_REFUSAL, AcpAgent, SessionContext, prompt_text  # noqa: E402

import guards  # noqa: E402

FILENAME = "watchd-conditions.json"

WELCOME = (
    "I am the sentry. Your words become a tracked watch:\n"
    "  - watch air quality in Denver over 150 every 5 minutes\n"
    "  - watch quakes within 120 km of Fresno over 4.5\n"
    "  - watch the river gauge at EADM7\n"
    "  - list my watches\n"
    "I write the conditions file with your permission, then print the activation lines. "
    "The watcher runtime itself (watchd) lives in the sibling repo: "
    "github.com/mrfentmen/awesome-servers (watchd/)."
)

IN_LIST = re.compile(r"\blist\b|\bshow\b|\bwhat (?:watches|conditions)\b|\binstalled\b", re.I)
_SWEPT = re.compile(r"\bsweep\b|\bcheck now\b|\brun it now\b", re.I)
_HELP = re.compile(r"^\s*(help|what can you do)\b", re.I)


def conditions_path(cwd: str) -> Path:
    return Path(cwd or ".") / "watches" / FILENAME


def render_list(doc: dict) -> str:
    checks = doc.get("checks") or []
    if not checks:
        return "No watches installed yet. Tell me one: watch air quality in Denver over 150."
    rows = []
    for row in checks:
        target = row.get("place") or row.get("gauge") or "?"
        if row.get("kind") == "air":
            rule = f"US AQI {row.get('threshold')} {row.get('when')}"
        elif row.get("kind") == "quakes":
            rule = f"M{row.get('magnitude', 4)} {row.get('when')} within {row.get('radius_km', 120)} km"
        else:
            rule = "at or over its published flood stage"
        rows.append(f"  - {row.get('name')}: watch {row.get('kind')} at {target} ({rule}), "
                    f"polls every {int(row.get('every_s', 300)) // 60} min")
    return "Watches installed:\n" + "\n".join(rows)


class SentryAgent(AcpAgent):
    name = "sentry"
    title = "Sentry - turns plain words into tracked watches for the watcher runtime"
    version = "1.0.0"

    def new_session(self, session) -> dict:
        session.remember("agent", "Sentry session opened. " + WELCOME.splitlines()[0])
        return {}

    def prompt(self, ctx: SessionContext, prompt: list[dict]) -> str:
        text = prompt_text(prompt)
        target = conditions_path(ctx.session.cwd or ".")
        ctx.plan([
            ("Parse the watch order (rules, no guessing)", "high"),
            ("Write the merged conditions file with your permission", "high"),
            ("Print the activation lines", "medium"),
        ])

        if not text or _HELP.search(text):
            ctx.stream_text(WELCOME)
            return STOP_END_TURN

        try:
            doc = json.loads(guards.read_json(target))
        except ValueError as exc:
            ctx.message(f"The existing conditions file is corrupt, so I touched nothing: {exc}")
            return STOP_END_TURN

        if IN_LIST.search(text) and not text.lower().lstrip().startswith("watch"):
            ctx.stream_text(render_list(doc) + "\n")
            ctx.message("Files live in watches/ - the watcher runtime reads them unchanged.")
            return STOP_END_TURN

        try:
            entry = guards.build_entry(text)
        except ValueError as exc:
            ctx.message(str(exc))
            return STOP_END_TURN

        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        merged, changed = guards.merge_into(json.dumps(doc), entry, now)
        relpath = target.relative_to(Path(ctx.session.cwd or ".")) \
            if target.is_relative_to(Path(ctx.session.cwd or ".")) else target

        write = "call_write_conditions"
        capabilities = (ctx.client_capabilities.get("fs") or {}) if ctx.client_capabilities else {}
        can_write = bool(capabilities.get("writeTextFile"))
        ctx.tool_call(write, f"{changed.capitalize()} watch {entry['name']}",
                      kind="edit", name="sentry-write",
                      raw_input={"path": str(target), "check": entry["name"]},
                      locations=[{"path": str(target)}])
        if not can_write:
            ctx.tool_call_update(write, status="failed",
                                 content=ctx.text_content("client advertises no filesystem write"))
            ctx.stream_text("This client does not advertise fs.writeTextFile, so I cannot install "
                            "the watch myself. Here is the conditions file to save by hand:\n\n"
                            "```json\n" + merged + "```\n\n" +
                            "\n".join(guards.activation_lines(str(relpath), entry["every_s"])) + "\n")
            ctx.message("Copy the JSON above into watches/" + FILENAME + " and hand the watcher "
                        "the activation lines.")
            return STOP_END_TURN

        if not ctx.ask_permission(write, f"Allow the sentry to {changed} the watch "
                                         f"{entry['name']} by writing {target}?",
                                  remember_key="sentry-write-watches"):
            ctx.tool_call_update(write, status="failed", content=ctx.text_content("permission denied"))
            ctx.message("Nothing was written. Say the watch again and accept the write to install it.")
            return STOP_REFUSAL
        ctx.tool_call_update(write, status="in_progress")

        try:
            ctx.conn.request("fs/write_text_file",
                             {"sessionId": ctx.session.id, "path": str(target), "content": merged},
                             timeout=30)
        except Exception as exc:  # JsonRpcError or transport closure: nothing written either way
            ctx.tool_call_update(write, status="failed", content=ctx.text_content(str(exc)[:160]))
            ctx.message(f"The editor refused the write ({exc}); nothing was saved. Here is the "
                        "conditions file to save by hand:\n\n```json\n" + merged + "```\n")
            return STOP_END_TURN

        ctx.tool_call_update(write, status="completed", content=ctx.text_content(f"wrote {target}"))
        activation = guards.activation_lines(str(relpath), entry["every_s"])
        ctx.stream_text(f"Watch {changed}: {entry['name']}.\n" + "\n".join(activation) + "\n")
        ctx.stream_text(self._sweep_hint(target))
        return STOP_END_TURN

    @staticmethod
    def _sweep_hint(target: Path) -> str:
        home = os.environ.get("AWESOME_SERVERS_HOME")
        if home and Path(home).exists():
            return ("You can check it fires correctly right now: the watcher runtime maps every "
                    "reading to the wording you would see in the yell.")
        return ("Set AWESOME_SERVERS_HOME to a checkout of mrfentmen/awesome-servers so the "
                "watcher runtime can be located for a live sweep; until then the watch stands "
                "installed but unverified.")

    def on_cancel(self, session) -> None:
        return None


def main(argv=None) -> int:
    import logging
    logging.basicConfig(level="INFO", stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        SentryAgent().run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
