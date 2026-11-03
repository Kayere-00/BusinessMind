"""Generate a realistic 2-year sample sales dataset for demos and tests."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = [
    ("Alpha Pro", "Software", 499.0), ("Beta Suite", "Software", 299.0),
    ("Gamma Device", "Hardware", 899.0), ("Delta Sensor", "Hardware", 349.0),
    ("Omega Support", "Services", 199.0),
]
CHANNELS = ["Online", "Retail", "Partner"]
SEGMENTS = ["Enterprise", "SMB", "Consumer"]


def generate(out_path: Path, rows: int = 4000) -> Path:
    start = date(2024, 1, 1)
    records = []
    for i in range(rows):
        # 2024-01-01 .. 2025-11-28 → complete calendar months only
        d = start + timedelta(days=random.randint(0, 696))
        product, category, price = random.choice(PRODUCTS)
        # Seasonality: Q4 uplift
        month_boost = 1.4 if d.month in (11, 12) else 1.0
        # Growth trend over time
        trend = 1.0 + (d - start).days / 696 * 0.5
        units = max(1, int(random.gauss(8, 4) * month_boost))
        revenue = round(units * price * trend, 2)
        cost = round(revenue * random.uniform(0.55, 0.75), 2)
        records.append([
            d.isoformat(), random.choice(REGIONS), product, category,
            random.choice(CHANNELS), random.choice(SEGMENTS),
            units, price, revenue, cost, round(revenue - cost, 2),
        ])

    # Inject a few obvious anomalies
    records.append(["2024-06-15", "North", "Gamma Device", "Hardware", "Online", "Enterprise", 900, 899.0, 809100.0, 600000.0, 209100.0])
    records.append(["2025-03-02", "South", "Omega Support", "Services", "Partner", "SMB", 1, 199.0, 0.01, 0.0, 0.01])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_date", "region", "product", "category", "channel",
                    "customer_segment", "units", "unit_price", "revenue", "cost", "profit"])
        w.writerows(records)
    return out_path


if __name__ == "__main__":
    out = generate(Path(__file__).resolve().parent.parent / "sample_data" / "sample_sales.csv")
    print(f"Wrote {out}")
