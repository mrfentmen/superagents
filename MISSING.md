# MISSING — what exists in the "superagent" world, what exists here, what stays unbuilt

This file is the claim-check. Every "first" claim in the README cites a search or a line in
this repo. Dated, verifiable, and open for contradiction — if a product below does everything
listed, say so and the claim moves.

## The name-check, run 2026-10-18

GitHub repository search, query `superagent agent`, sort stars: **327 repositories**. The
leaders, at that date:

| Repo | Stars | What it calls itself |
|---|---|---|
| bytedance/deer-flow | 84,031 | "an open-source long-horizon SuperAgent harness" — research, coding, creativity |
| iflytek/astron-agent | 8,911 | "enterprise-grade agentic workflow platform" |
| superagentxai/superagentx | 203 | "policy-driven autonomous AI agents" |

Framework-level "superagent" is a crowded shelf: harnesses, workflow platforms, policy
engines. What the leaders do not do, per their own documentation and feature lists checked
on the date above (read them; anything contradicted by a doc link moves out of this file):

1. they do not spawn real sibling agents as protocol children and merge their answers with
   per-row citations — federation theirs is model-or-workflow inside one process;
2. they do not answer real-world questions from keyless public datasets with the source named
   in every answer;
3. they do not author persistent watches from one plain sentence, installed through a
   protocol permission step into a file an independent watcher runtime obeys;
4. deterministic, offline-testable routing over a manifest file, with the ranking shown to
   the user, is not among their features.

## Claims this repo makes, each with its proof

- **Agents as feeds (generalized).** Proven in the sibling repo by the
  [`orchestrator`](https://github.com/mrfentmen/awesome-servers/tree/main/acp/agents/orchestrator)
  (session 8 of its MISSING.md, live smoke recorded there). The polymath generalizes it:
  registry as data, topic-word routing, in-repo handoff to the watch creature. Proof here:
  the federation tests spawn real child processes; the live cross-repo smoke on 2026-10-17
  had the air agent answer US AQI 43 for Denver through the bridge.
- **Words to watch.** The sentry parses one sentence into a check, writes it behind the
  protocol's permission step, and prints the activation lines. The editor-side write
  (`fs/write_text_file`) behind `session/request_permission` — a pair that a GitHub search
  on 2026-09-30 (recorded in the sibling repo's MISSING.md) found unused by any ACP agent
  in the wild — is exactly what this creature makes load-bearing. Strongest test: a real
  child install into a sandboxed fs root, bytes checked.
- **The unclaimed coverage.** Official push services exist for the big three hazards: USGS
  WaterAlert (free gauge-threshold email/text, verified live 2026-10-18),
  USGS Earthquake Notification Service, EPA's AirNow notification service, NWS weather
  alerting. Those cover a handful of hazard families. The sibling corpus watches hundreds of
  datasets with **no official notification channel anywhere** — tides crossing, radiation
  anomalies, species occurrences, launches, pollen, pageviews. The claims here are about
  that territory, never about replacing the government's channels.

## What stays unbuilt (honest ledger)

- A **watch-skill inside the polymath's briefs** — "brief me, and pin it as a watch" (brief +
  install in one turn). Two turns today; single-turn is not built.
- **Composite watch linkages** ("yell when air over 150 AND a quake M4+"): the watcher's
  check grammar is per-check only; AND/OR combinations are not built.
- **Genuinely pushing feeds** (websocket, SSE) as sibling sources: every sibling today is
  polled. The sibling repo's MISSING.md has the same open line.
- **Untrusted-sibling sandboxing**: a spawn runs the sibling with full process rights; an
  editor-grade sandbox across spawn trees is out of scope here and must not be assumed.
- **Live sweep inside the sentry session** (run the watcher one pass from within the turn):
  planned via `AWESOME_SERVERS_HOME`, not wired; today the creature prints activation lines
  and its hint says so honestly.

## Contribute a sibling

Edit `agents/polymath/registry.json` — name, directory (with either `AWESOME_SERVERS_HOME`
as the sibling repo's checkout path, or `internal: true` if the creature lives here), the ask
template, and topic words. Reload. No code changes required; the tests cover the
registry-driven routing.
