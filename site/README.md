# Results website

The pages at <https://rullst.win/Benchmarks/>, rendered from the files under
`../results/` by this Rust program with Rullst's `html!` macro (the published
`rullst` crate, version pinned in `Cargo.toml`; the footer of every page names
it). The program has no numbers of its own: it reads `latest.json`,
`site.json`, `versions.json` and `rullst/<version>.json`, checks them and
writes static HTML with one stylesheet. The pages have no JavaScript, and a
Content-Security-Policy meta tag allows only the site's own stylesheet and icon.

```sh
cargo run --locked -- --results ../results --out ../_site
```

`--today YYYY-MM-DD` sets the date the age check uses (default: today, UTC),
`--max-age-days N` the age limit (default 90), and `--require-results` makes a
"results pending" outcome an error instead of a page.

## Results pending

Every page says "results pending" and shows no numbers when a file is missing
or not valid JSON, when a schema, category, status, stability result, flag or
overall weighting is one the pages do not explain, when `site.json` or
`versions.json` describe another run than `latest.json`, when a position or
score is out of range, or when the results were measured more than the age
limit before today or after it. These are the rules the Rullst website applies
to `site.json`. The deploy workflow re-renders the pages daily so that the age
limit takes effect without a new commit.

## Pages

| Path | Content |
| --- | --- |
| `/` | the run, how to read the scores, the overall ranking (position ranges, ±, flags), the other weightings, the reading for Rullst (English, and Brazilian Portuguese from `site.json`), one card per category |
| `/hello/` … `/startup/`, `/stability/` | one ranking per category with its tie groups, the per-endpoint ratios, the diagnostics and the A/A control apart, and how each position was decided |
| `/endpoints/` | the summary tables, one table per Tier 1 endpoint, hot rows, Tiers 2 to 4 (memory with the peak after the logins) |
| `/diagnostics/` | axum-no-ping, Rullst minimal and the A/A control, with the tie margins the control gives |
| `/implementations/`, `/implementations/<slug>/` | versions, settings, notes, runner CPUs and scores of each implementation |
| `/history/` | the Rullst variants across measured versions, with each run's load generator |
| `/method/` | the measurement settings and scoring rules from the results, the environment, the publication gate, links to the README |

The pages are in English. Only the reading for Rullst exists in Brazilian
Portuguese in the data (`site.json`); the rest would need translations kept by
hand, so the pages show that reading and nothing else in Portuguese.

## Tests

`cargo test` renders `tests/fixtures/results/` (the 13.0.0-alpha.6 results,
trimmed by `tests/fixtures/trim.py`, with markup injected into some text fields)
and checks every page: document structure, landmarks, the policy, balanced
elements, escaping, internal links, the footer, and the "results pending" page
of each rule above. CI also renders the published `results/` as of the day they
were measured, so a change to their shape that the pages do not read fails
there.
