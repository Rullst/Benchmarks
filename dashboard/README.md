# Dashboard

The page at <https://rullst.win/Benchmarks/>. It has no numbers of its own: at
run time it fetches `data/latest.json` and `data/versions.json`, which the
deploy workflow copies from `../results/` (written by `bench/aggregate.py`).

```sh
npm ci
mkdir -p public/data && cp ../results/latest.json ../results/versions.json public/data/ && cp -R ../results/rullst public/data/
npm run dev
```

Without data the page says that no results have been published yet.
