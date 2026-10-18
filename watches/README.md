# watches — the runtime folder

Files here are written by the sentry creature with your permission, and read by the watcher
runtime in the sibling repo ([`watchd/`](https://github.com/mrfentmen/awesome-servers/tree/main/watchd),
located on your machine with `AWESOME_SERVERS_HOME`). One JSON file per picket line; the file
is the whole contract: no registry, no database, no private channel between the creature that
writes and the watcher that obeys.

Defaults when the sentry writes: console notifier on; every check keeps the polling interval
it was ordered with. Edit by hand, restart the watcher, done.

Nothing in this folder is required for the creatures' tests: they run in temporary roots.
