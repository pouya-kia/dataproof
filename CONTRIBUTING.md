# Contributing

DataProof values small, reviewable changes with executable evidence. Start with a failing adversarial example or a precise semantics gap, describe the declared schema and bound, then run the focused test, affected regression suite and full gate in [testing strategy](docs/testing-strategy.md). Use Angular-style Conventional Commits such as `test(parser): reject unsupported window syntax`. Do not turn a bounded miss into a proof claim or upload private data.

For a research comparison, record exact source/version/license, input mapping, commands, environment, timeouts and every failure. Keep outcome wording in the [claims ledger](research/claims_ledger.md). Pull requests should state the obligation, supported fragment, tests run and any unverified platform. Small first contributions include a new negative SQL fixture, a replay corruption test, or a documented competitor setup attempt. Please open an issue first for a change to the formal fragment or status contract.
