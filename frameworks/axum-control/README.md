# Axum (A/A control)

An identical copy of [the Axum baseline](../axum): every file except
`bench.json` and this README is byte-identical to `frameworks/axum`
(`python3 bench/harness.py validate` fails if one differs). It is measured
exactly like every other implementation: its own jobs, its own image built
from this folder, rounds in ABBA order against Axum on the same runner.

What it is for: its scores should all be 1.00, so how far they land from
1.00 is the noise a score carries (runner-to-runner and round-to-round
variation, and anything the harness does differently to the two sides of a
job). Its largest deviation from 1.00, per job and pooled, is each
category's A/A margin. That margin is one of three terms of the tie margin;
the others are the two implementations' spread between their own jobs and a
pooled floor (see section 12 of `docs/v3-spec.md`). A score within the A/A
margin of 1.00 is marked as not distinguishable from Axum. The publication
gate refuses results whose A/A margin is above `publication.max_aa_margin` in
`bench/config.json`.

It is not ranked and has no position. Keep it in sync with `frameworks/axum`:
copy every changed file here in the same commit.
