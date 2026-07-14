"""End-to-end tablegold demo: a tiny aggregation pipeline and its golden file.

Run it with an output directory:

    python examples/pipeline_demo.py /tmp/out

The demo tells the whole story in three acts:

1. ``summarize`` is "pipeline v1" — the run that blessed the committed
   golden (``examples/goldens/daily_metrics.csv``).
2. ``summarize_sorted`` is "pipeline v1.1" — the same math folded in a
   different order. Float addition is not associative, so the numbers
   differ in the last bits; tablegold still reports MATCH.
3. ``summarize_discounted`` is a regression — a bulk discount leaked into
   the revenue metric. The drift is small but real, and tablegold reports
   exactly which cells moved and by how much.

Everything is deterministic: fixed input data, no randomness, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tablegold import Table, compare, render_text

GOLDEN = Path(__file__).parent / "goldens" / "daily_metrics.csv"

#: (order_id, region, units, unit_price) — one deterministic day of orders.
#: The 4-decimal unit prices are FX-converted rates; they make the regional
#: revenue sums genuinely fold-order-sensitive (last-bit float noise).
RAW_ORDERS = [
    ("A-1001", "east", 3, 40.559),
    ("A-1002", "west", 6, 162.7128),
    ("A-1003", "east", 1, 25.0),
    ("A-1004", "north", 6, 115.795),
    ("A-1005", "west", 6, 44.4424),
    ("A-1006", "east", 3, 212.1786),
    ("A-1007", "north", 2, 63.1636),
    ("A-1008", "west", 2, 42.524),
    ("A-1009", "east", 3, 202.1678),
    ("A-1010", "north", 5, 67.1599),
    ("A-1011", "west", 3, 247.4018),
    ("A-1012", "east", 4, 134.985),
]


def _aggregate(orders):
    """Group orders per region, preserving the iteration order given."""
    per_region = {}
    for _order_id, region, units, unit_price in orders:
        bucket = per_region.setdefault(region, {"orders": 0, "units": 0, "revenue": 0.0})
        bucket["orders"] += 1
        bucket["units"] += units
        bucket["revenue"] += units * unit_price
    return [
        {
            "region": region,
            "orders": bucket["orders"],
            "units": bucket["units"],
            "revenue": bucket["revenue"],
            "avg_unit_price": bucket["revenue"] / bucket["units"],
        }
        for region, bucket in sorted(per_region.items())
    ]


def summarize(orders=RAW_ORDERS):
    """Pipeline v1: fold line items in input order (blessed the golden)."""
    return _aggregate(orders)


def summarize_sorted(orders=RAW_ORDERS):
    """Pipeline v1.1: identical math, different fold order -> float noise."""
    return _aggregate(sorted(orders, key=lambda order: (order[1], order[3])))


def summarize_discounted(orders=RAW_ORDERS):
    """A regression: a bulk discount silently applied to large orders."""
    discounted = [
        (order_id, region, units, unit_price * 0.999 if units >= 5 else unit_price)
        for order_id, region, units, unit_price in orders
    ]
    return _aggregate(discounted)


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Act 2: the reimplementation only introduces sub-tolerance float noise.
    v11 = Table.from_rows(summarize_sorted(), source="metrics_v1_1.csv")
    v11.write_csv(out / "metrics_v1_1.csv")
    noise = compare(GOLDEN, out / "metrics_v1_1.csv", key=["region"], rtol=1e-9)
    print("[v1.1] fold-order noise vs golden: %s" % ("MATCH" if noise.ok else "MISMATCH"))

    # Act 3: the discount regression must be caught, with receipts.
    bad = Table.from_rows(summarize_discounted(), source="metrics_discounted.csv")
    bad.write_csv(out / "metrics_discounted.csv")
    regression = compare(GOLDEN, out / "metrics_discounted.csv", key=["region"], rtol=1e-9)
    print("[regression] discount change vs golden: %s" % ("MATCH" if regression.ok else "MISMATCH"))
    print(render_text(regression))

    if not noise.ok or regression.ok:
        return 1
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python examples/pipeline_demo.py OUT_DIR", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
