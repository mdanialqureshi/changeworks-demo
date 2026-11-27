# Cloud check

`changeworks cloud-check` opens a fixture issue in this repository and
runs it through the deployed factory with the scripted engine, which
replays recorded answers and calls no model, so the run costs $0. The
item goes through triage, the spec, Gate 1, implement, verify, review
and repository CI to Gate 2, where the check refuses it. The pull
request and the issue are then closed; nothing is merged.
