"""The polymath: one question in, the most fitting creatures answering under it.

Not a framework and not a harness: a working ACP agent. Its skills:

  - brief <place>            fan the place out to every registered sibling, merge the rows
  - ask <sibling>: <words>   one hop, forwarded verbatim
  - who should answer: ...   topic-scored ranking of the siblings for an unformed question
  - watch <condition> ...    spawns the watch creature (sentry) as a child and hands off
  - catalog / help

Everything is cited: each row names which agent said it, and a sibling that failed is a
named failure, never silence.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for path in (str(REPO / "kit"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from acp_kit import STOP_END_TURN, STOP_REFUSAL, AcpAgent, SessionContext, prompt_text  # noqa: E402

import federation as fed  # noqa: E402

PERMISSION_KEY = "polymath-spawn-siblings"

ABOUT = (
    "I am the polymath. I hold a registry of sibling agents (agents/polymath/registry.json) "
    "and spawn the fitting ones as real child processes, merge their answers into one reply, "
    "and cite each row. Ask me:\n"
    "  - brief me on Denver\n"
    "  - ask moon: when is the next full moon?\n"
    "  - who should answer: is the beach safe in Boston?\n"
    "  - watch air quality in Denver, yell over 150\n"
    "  - what siblings do you have?\n"
)
_BRIEF = re.compile(r"\bbrief\b", re.I)
_FIND = re.compile(r"who(?:'s| is|s| should answer| can answer| handles)\b[:\s]|which sibling", re.I)
_CATALOG = re.compile(r"\bwhat siblings\b|\bcatalog\b|\bwho do you know\b|\blist (?:your )?agents\b", re.I)
_HELP = re.compile(r"^\s*(help|what can you do)\b", re.I)


def route(text: str) -> tuple[str, dict]:
    """Deterministic routing. Pure; offline-testable."""
    stripped = str(text or "").strip()
    if not stripped or _HELP.search(stripped):
        return "help", {}
    if _CATALOG.search(stripped):
        return "catalog", {}
    if _FIND.search(stripped):
        return "find", {"query": _FIND.sub("", stripped).strip(" :?") or stripped}
    pair = fed.ask_pair(stripped)
    if pair:
        return "ask", {"agent": pair[0], "question": pair[1]}
    if any(w in stripped.lower() for w in fed.watch_words()):
        return "hire", {"order": stripped}
    if _BRIEF.search(stripped):
        place = fed.place_of(stripped)
        if place:
            named = fed.topics_on(stripped)
            return "brief", {"place": place, "topics": named}
    # an unformed question falls through to the ranking, which either names a domain or abstains
    ranking = fed.find_ranking(stripped)
    if ranking:
        return "ask", {"agent": ranking[0]["agent"], "question": stripped}
    return "help", {}


def clamp(text: str, lines: int = 4) -> str:
    rows = [ln for ln in (text or "").splitlines() if ln.strip()]
    if len(rows) <= lines:
        return "\n".join(rows) or "(no answer)"
    return "\n".join(rows[:lines]) + f"\n  ... +{len(rows) - lines} more line(s) from the agent"


def render_brief(place: str, rows: list) -> tuple[str, str]:
    good = [r for r in rows if r.ok and r.text]
    bad = [r for r in rows if not (r.ok and r.text)]
    lines = [f"Brief for {place} - {len(good)} of {len(rows)} sibling agents answered:"]
    for row in good:
        lines.append(f"\n[{row.agent}]")
        lines.append(clamp(row.text))
    for row in bad:
        lines.append(f"\n[{row.agent}] not answered: {row.error or 'refused the question'}")
    return ("\n".join(lines) +
            "\n\nSource: named sibling agents, each spawned as its own process (ACP over stdio); "
            "every row above cites the agent that produced it."), f"{len(good)}/{len(rows)} sibling answers"


class PolymathAgent(AcpAgent):
    name = "polymath"
    title = "Polymath - routes your question to the fitting sibling agents and merges their answers"
    version = "1.0.0"

    def new_session(self, session) -> dict:
        session.remember("agent", "Polymath session opened. " + ABOUT.splitlines()[0])
        return {}

    def prompt(self, ctx: SessionContext, prompt: list[dict]) -> str:
        text = prompt_text(prompt)
        skill, params = route(text)
        ctx.plan([
            (f"Route the request ({skill})", "high"),
            ("Spawn the fitting sibling(s)", "high"),
            ("Merge, cite, and answer", "medium"),
        ])

        if skill == "help":
            ctx.stream_text(ABOUT)
            return STOP_END_TURN

        if skill == "catalog":
            rows = fed.catalog_rows()
            body = "\n".join(
                f"  - {r['agent']}: {r['ask_example']}" for r in rows)
            ctx.stream_text("Siblings I can spawn:\n" + body +
                            "\n\nRegistry file: agents/polymath/registry.json (data, not code - "
                            "add a row and reload me).\n")
            ctx.message("A failing sibling is a named row in the brief, never silence.")
            return STOP_END_TURN

        if skill == "find":
            ranking = fed.find_ranking(params["query"])
            body = "\n".join(f"  - {r['agent']} (topic words: {', '.join(r['hits'])})"
                             for r in ranking[:3]) or "  (no sibling's topic words match)"
            ctx.stream_text("For " + params["query"] + ", the leading siblings:\n" + body + "\n")
            ctx.message("The ranking is word-scoring over the registry, not an LLM opinion - "
                        "deterministic and testable (see find_ranking).")
            return STOP_END_TURN

        body_lines, summary = "", ""
        if skill == "ask":
            tool = "call_ask"
            target_title = f"Run the {params['agent']} sibling"
            names, questions = [params["agent"]], {params["agent"]: params["question"]}
        elif skill == "hire":
            ctx.stream_text(
                "Watches belong to the sentry, my sibling in this repo. Handing over...\n")
            child = fed.run_sibling(fed.watch_handler(), params["order"])
            ctx.stream_text((child.text or "(the sentry returned an empty answer)") +
                            f"\n\nSource: the {fed.watch_handler()} creature, spawned over ACP.\n")
            ctx.message("The watch lives in the watches/ file the sentry wrote; the activation "
                        "line it printed is the whole operational contract.")
            return STOP_END_TURN
        else:
            tool = "call_brief"
            names = params["topics"] or sorted(fed.siblings())
            target_title = f"Run {len(names)} siblings"
            questions = {name: fed.sibling_question(fed.siblings()[name],
                                                    params["place"] or "") for name in names}

        ctx.tool_call(tool, target_title, kind="run", name=tool, raw_input=params)
        if not ctx.ask_permission(tool, "Allow the polymath to start sibling agent processes "
                                        "and read their answers?", remember_key=PERMISSION_KEY):
            ctx.tool_call_update(tool, status="failed", content=ctx.text_content("permission denied"))
            ctx.message("I need your permission before starting other agent processes.")
            return STOP_REFUSAL
        ctx.tool_call_update(tool, status="in_progress")

        rows = fed.fan_out(questions)
        failures = [f"{r.agent}: {r.error}" for r in rows if not r.ok and r.error]
        if skill == "ask" and len(rows) == 1 and not rows[0].ok and rows[0].error:
            ctx.tool_call_update(tool, status="failed", content=ctx.text_content(rows[0].error))
            ctx.message(f"The sibling failed honestly: {rows[0].error}")
            return STOP_END_TURN

        if skill == "ask":
            row = rows[0]
            body_lines = (row.text or "(empty answer)") + \
                f"\n\nSource: the {row.agent} agent, spawned over ACP by the polymath."
            summary = f"{row.agent}: stopReason={row.stop_reason or 'end-turn'}"
        else:
            body_lines, summary = render_brief(params["place"] or "your place", rows)
        if failures and skill != "ask":
            summary += f" ({len(failures)} named failure(s))"

        ctx.tool_call_update(tool, status="completed", content=ctx.text_content(summary))
        ctx.stream_text(body_lines + "\n")
        return STOP_END_TURN

    def on_cancel(self, session) -> None:
        return None


def main(argv=None) -> int:
    import logging
    logging.basicConfig(level="INFO", stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        PolymathAgent().run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
