# superagents — two creatures, not a framework

This repo holds working ACP agents that answer **real-world questions** by running other,
working agents, and that create **persistent watches** from plain words. Everything is
keyless, cited, and tested offline. It is not a harness, not a server, not an API-key
framework — it is two small creatures with tests you can read in one sitting.

| Creature | What it does in one line | Tests |
|---|---|---|
| [`agents/polymath`](agents/polymath) | spawns sibling domain agents as real child processes over ACP, merges a brief, and cites every row (including the ones that failed) | 20 |
| [`agents/sentry`](agents/sentry) | turns "watch air quality in Denver over 150" into a conditions file the watcher runtime obeys — one protocol write, behind your permission | 15 |

## Why this is a different creation from what exists

The "superagent" shelf on GitHub is frameworks and harnesses for building assistants. Dated
numbers from the name-check run for this repo ([`MISSING.md`](MISSING.md) holds the full
record): 327 repositories under `superagent agent` search; the largest is a long-horizon
research/coding harness (84,031 stars); the next tier are workflow platforms. What **none**
of those products do, per their own docs and feature lists at the time of writing:

1. **Run real, independently-versioned sibling agents as protocol children.** A brief here is
   not one model simulating domains; it is five processes, each the same code a user would
   run, each answering in its own shape, each cited by name. A sibling that fails is a named
   row, never a simulated success.
2. **Answer from keyless public data.** No keys, no credits, no rate-limit roulette.
3. **Author watches.** You say the watch; the creature writes it (with a permission step the
   protocol supplies) into a file that the sibling repo's watcher runtime obeys unchanged.
   The file is the entire contract.
4. **Show its work.** Routing is ranked word-matching over a manifest file (`registry.json`
   is data, not code), deterministic and offline-testable — not an unprompted LLM opinion.

The honest file about what remains unbuilt and what was checked before claiming any of it:
[`MISSING.md`](MISSING.md).

## Quick start

```bash
# polymath needs a checkout of the answerer repo (its siblings live there):
git clone https://github.com/mrfentmen/awesome-servers
export AWESOME_SERVERS_HOME=$PWD/awesome-servers

python3 agents/polymath/agent.py     # speak ACP over stdio (editors spawn it like any agent)
python3 agents/sentry/agent.py       # the watch creature: "watch air quality in Denver over 150"
```

Prompt lines an editor session can feed the polymath:

```
brief me on Denver
ask moon: when is the next full moon?
who should answer: is the beach safe in Boston?
watch air quality in Denver over 150           → handed to the sentry
what siblings do you have?
```

## The kit

`kit/` vendors the ACP kit used by the sibling repo's 79 agents (agent half, client half,
jsonrpc). The creatures use the client half to spawn their siblings — the editor-side half
of the protocol, used by an agent, which is itself the first claim in
[`MISSING.md`](MISSING.md) to be verified by search rather than asserted.

## Run the tests

```bash
python3 agents/polymath/tests/test_agent.py   # 20 tests, offline
python3 agents/sentry/tests/test_agent.py     # 15 tests, offline
```

The federation tests spawn a real (tiny, offline) ACP responder as a child process, so the
child supervision is exercised exactly as it runs in production; the sentry's strongest test
spawns the real creature and installs a watch through the kit's own filesystem server into a
temporary root, then checks the JSON it wrote.
