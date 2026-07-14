# Comparison semantics

This document is the precise contract behind every `MATCH`/`MISMATCH`
verdict. If a rule here changes, the change is breaking and bumps the minor
version (and `report_version` for the JSON report).

## Findings model

A comparison produces three kinds of findings:

| Kind | Examples | Fails the comparison? |
| --- | --- | --- |
| error | missing column, incompatible dtype, row-count/keys, strict-mode violations | yes |
| cell diff | value outside tolerance, hole vs value, string drift | yes |
| note | column order changed, row order changed (keyed), int/float widening, allowed extra column | no |

`ok` is true iff there are zero errors and zero cell diffs.

## Dtype inference

Every cell is a raw string; each column gets one inferred dtype, most
specific first: `bool > int > float > date > datetime > string`, plus
`empty` for an all-missing column.

| Dtype | Accepted forms |
| --- | --- |
| bool | `true` / `false`, any case |
| int | optional sign + digits (`42`, `-7`, `+0`) |
| float | anything `float()` accepts except underscores: `1.5`, `2.5e0`, `NaN`, `inf`, `-Infinity` |
| date | strict ISO `YYYY-MM-DD` |
| datetime | strict ISO 8601: `T` or space separator, optional `:SS[.ffffff]`, optional zone `Z` / `+HH:MM` / `+HHMM` |
| string | everything else, compared raw and unstripped |

Mixing rules are conservative: `int`+`float` widens to `float`; every other
mix (`bool`+`int`, `date`+`datetime`, anything+`string`) degrades to
`string`, because guessing would hide bugs. `empty` is compatible with any
dtype. `strict_dtypes=True` turns any golden-vs-actual dtype difference into
an error and skips value comparison for that column.

## Missing values

The empty string and the case-insensitive tokens `NA`, `N/A`, `NULL`, `None`
(after stripping whitespace) are missing in every dtype. Two missing cells
are equal regardless of spelling; a missing cell never equals a value. `NaN`
is **not** missing — it is the IEEE-754 float, and `NaN == NaN` by default
(`nan_equal=False` opts out).

## Numeric closeness

Floats are equal when

```text
|a - b| <= max(atol, rtol * max(|a|, |b|))
```

with defaults `rtol=1e-9`, `atol=1e-12`. The predicate is symmetric
(swapping golden and actual never changes the verdict — unlike
`numpy.isclose`, which scales by `|b|` only). Infinities are equal only to
the same-signed infinity and never close to any finite number. Integer
columns compare exactly; an int column against a float column is compared
as floats under the column's tolerance. Per-column overrides
(`column_tolerances={"revenue": Tolerance(rtol=1e-6)}`, CLI `--tol
revenue:1e-6`) replace the defaults for that column completely.

## Row alignment

Without `key`, rows pair by position and a row-count difference is an
error. With `key=["id", ...]`, rows pair by the stripped key-cell values:
missing keys, unexpected keys, and duplicate keys (which are excluded from
value comparison as ambiguous) are errors reported with example key values,
and a changed row order is only a note.

## Exit codes (CLI)

| Code | Meaning |
| --- | --- |
| 0 | tables match (notes allowed) |
| 1 | mismatch: at least one error or cell diff |
| 2 | usage or read error (bad flags, malformed/unreadable file) |
