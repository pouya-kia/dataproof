# Offline NoUndo demo cue sheet

This is a screen-recording cue sheet, not a claim that setup or installation takes a measured amount of time. Install once as shown in the README, then record the following actual local terminal commands without editing their output:

```sh
.venv/bin/dataproof check examples/no_undo/daily_distinct.json --output artifacts/demo
.venv/bin/dataproof replay artifacts/demo/witness.json
.venv/bin/python -c 'import duckdb; con=duckdb.connect(":memory:", config={"enable_external_access":"false"}); print(con.execute(open("artifacts/demo/replay.sql").read()).fetchall())'
```

Show the two monthly values and equal retained daily rows in `artifacts/demo/witness.json`, then show the final `REPLAY_OK` assertion in `artifacts/demo/replay.sql` using a local DuckDB execution. The CLI's replay command already executes the serialized SQL independently. State the precise interpretation: the retained daily view fails to determine monthly distinct customers under this finite schema; no backup deletion or universal determinacy result is implied. Do not present a recording until the commands and unaltered logs have been rerun on the recording machine.
