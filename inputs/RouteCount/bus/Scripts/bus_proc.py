from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# Paths
# ============================================================
INPUT_DIR = Path("./20251216_Raw_RouteCounts")
OUTPUT_DIR = Path("./20251216_Processed_RouteCounts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = INPUT_DIR / "MBTA_Bus_Ridership_by_Trip_Season_Route_Line_and_Stop_Fall_2024.csv"

# ============================================================
# Constants
# ============================================================
SILVER_LINE_IDS = ['741', '742', '743', '751', '749', '746']
DAY_TYPE = "weekday"

BUS_TARGET_SUM = 299_374
SILVER_LINE_TARGET_SUM = 33_236

# ============================================================
# Helper functions
# ============================================================
def scale_to_target(df, value_col, target_sum):
    scale_factor = target_sum / df[value_col].sum()
    df_scaled = df.copy()
    df_scaled[value_col] *= scale_factor
    return df_scaled, scale_factor

# ============================================================
# Load data
# ============================================================
if not DATA_FILE.exists():
    raise FileNotFoundError(f"File not found: {DATA_FILE.resolve()}")

df = pd.read_csv(DATA_FILE, low_memory=False)
print(f"Loaded {len(df):,} rows and {len(df.columns):,} columns")

# ============================================================
# Aggregate boardings by route and day type
# ============================================================
agg_boardings = (
    df.groupby(['route_id', 'day_type_name'], as_index=False)['boardings']
      .sum()
      .rename(columns={'boardings': 'total_boardings'})
)

agg_boardings = (
    agg_boardings
    .query("day_type_name == @DAY_TYPE")
    .sort_values(['route_id', 'total_boardings'], ascending=[True, False])
)

# ============================================================
# Split bus vs Silver Line
# ============================================================
agg_silver = agg_boardings[agg_boardings['route_id'].isin(SILVER_LINE_IDS)].copy()
agg_bus = agg_boardings[~agg_boardings['route_id'].isin(SILVER_LINE_IDS)].copy()

assert len(agg_boardings) == len(agg_bus) + len(agg_silver)

print(f"Bus total (raw): {agg_bus['total_boardings'].sum():,.1f}")
print(f"Silver Line total (raw): {agg_silver['total_boardings'].sum():,.1f}")

# ============================================================
# Scale boardings to control totals
# ============================================================
agg_bus_scaled, bus_scale_factor = scale_to_target(
    agg_bus, "total_boardings", BUS_TARGET_SUM
)

agg_silver_scaled, silver_scale_factor = scale_to_target(
    agg_silver, "total_boardings", SILVER_LINE_TARGET_SUM
)

print(f"Bus scale factor: {bus_scale_factor:.6f}")
print(f"Silver Line scale factor: {silver_scale_factor:.6f}")

# ============================================================
# Save outputs
# ============================================================
agg_bus_scaled.to_csv(
    OUTPUT_DIR / "agg_bus_boardings_scaled.csv", index=False
)

agg_silver_scaled.to_csv(
    OUTPUT_DIR / "agg_sl_boardings_scaled.csv", index=False
)

# ============================================================
# Summary statistics (weekday)
# ============================================================
tb = agg_boardings['total_boardings']
agg_stats = pd.Series({
    "count": tb.count(),
    "sum": tb.sum(),
    "mean": tb.mean(),
    "median": tb.median(),
    "std": tb.std(),
    "min": tb.min(),
    "max": tb.max()
})
print("\nAggregate statistics:")
print(agg_stats)

# ============================================================
# Per-route totals and shares
# ============================================================
per_route = (
    agg_boardings
    .groupby('route_id', as_index=False)['total_boardings']
    .sum()
    .sort_values('total_boardings', ascending=False)
)

per_route['pct_share'] = per_route['total_boardings'] / per_route['total_boardings'].sum()
per_route['cum_share'] = per_route['pct_share'].cumsum()

per_route.to_csv(
    OUTPUT_DIR / "weekday_boardings_per_route_with_shares.csv",
    index=False
)

# ============================================================
# Quick plot (top 20 routes)
# ============================================================
(
    per_route
    .set_index('route_id')['total_boardings']
    .head(20)
    .plot(kind='bar', figsize=(10, 4), title="Top 20 Routes — Weekday Boardings")
)

plt.ylabel("Total Boardings")
plt.tight_layout()
plt.show()
