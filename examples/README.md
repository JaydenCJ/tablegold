# tablegold examples

Two runnable pieces, one committed golden file.

## `pipeline_demo.py` — the whole story in one script

```bash
python examples/pipeline_demo.py /tmp/tablegold-demo
```

It aggregates a fixed day of orders three ways:

1. **v1** — the implementation that blessed `goldens/daily_metrics.csv`;
2. **v1.1** — identical math, different fold order. Float addition is not
   associative, so every regional revenue differs in the last bits; the
   comparison still reports `MATCH` under `rtol=1e-9`;
3. **a regression** — a bulk discount leaks into the metric. The report
   pinpoints the two drifted regions in `revenue` and `avg_unit_price`,
   with absolute and relative magnitudes, and the script exits non-zero
   territory only if the verdicts are wrong (it prints `DEMO OK` when the
   noise passes *and* the regression is caught).

## `test_metrics_pipeline.py` — the same guarantees as a pytest suite

These tests run as part of the repository suite (`pytest` from the repo
root picks up `examples/` via `testpaths`). They use the `tablegold`
fixture against the committed golden:

```bash
pytest examples/
TABLEGOLD_UPDATE=1 pytest examples/   # re-bless after an intended change
```

`goldens/daily_metrics.csv` is the golden both pieces share. Regenerate it
only through the update flow above; it is canonical output, not hand-written.
