from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- Configuration ---
INPUT_DIR = Path("./20251216_Raw_RouteCounts")
OUTPUT_DIR = Path("./20251216_Processed_RouteCounts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Note: Using the specific filename from your snippet
DATA_FILE = INPUT_DIR / "MBTA_Commuter_Rail_Ridership_by_Trip%2C_Season%2C_Route_Line%2C_and_Stop..csv"

DAY_TYPE = "weekday"
SEASON_FILTER = "Fall 2024"
CR_TARGET_SUM = 111_755

# --- Helper Functions ---
def scale_to_target(df, value_col, target_sum):
    """Scales a numeric column so its sum matches the target."""
    current_sum = df[value_col].sum()
    if current_sum == 0:
        return df, 0
    scale_factor = target_sum / current_sum
    df_scaled = df.copy()
    df_scaled[value_col] *= scale_factor
    return df_scaled, scale_factor

# --- Main Script ---

if not DATA_FILE.exists():
    raise FileNotFoundError(f"File not found: {DATA_FILE.resolve()}")

# 1. Load and Filter
df = pd.read_csv(DATA_FILE, low_memory=False)
df = df[df['season'] == SEASON_FILTER].copy()
print(f"Loaded {len(df):,} rows for {SEASON_FILTER}")

# Export filtered raw data
df.to_csv(OUTPUT_DIR / "MBTA_Commuter_Rail_Ridership_Fall2024.csv", index=False)

# 2. Aggregate boardings (average_ons)
agg_boardings = (
    df.groupby(['route_id', 'day_type_name'], as_index=False)['average_ons']
    .sum()
    .rename(columns={'average_ons': 'total_boardings'})
)

# Filter for Weekday and Sort
agg_boardings = (
    agg_boardings
    .query("day_type_name == @DAY_TYPE")
    .sort_values(['route_id', 'total_boardings'], ascending=[True, False])
)

# 3. Scale to Control Totals
agg_cr_scaled, cr_scale_factor = scale_to_target(
    agg_boardings, "total_boardings", CR_TARGET_SUM
)

print(f"Commuter Rail total (raw): {agg_boardings['total_boardings'].sum():,.1f}")
print(f"Scale factor applied: {cr_scale_factor:.6f}")
print(f"Scaled sum: {agg_cr_scaled['total_boardings'].sum():,.1f}")

# 4. Save Scaled Results
agg_cr_scaled.to_csv(
    OUTPUT_DIR / "agg_commuter_rail_boardings_scaled.csv", 
    index=False
)

# 5. Statistics and Share Analysis
tb = agg_boardings['total_boardings']
agg_stats = pd.Series({
    'count': tb.count(),
    'sum': tb.sum(),
    'mean': tb.mean(),
    'median': tb.median(),
    'std': tb.std(),
    'min': tb.min(),
    'max': tb.max()
})
print("\nAggregate Statistics (Weekday Raw):")
print(agg_stats)

# Calculate shares
per_route = (
    agg_boardings
    .groupby('route_id', as_index=False)['total_boardings']
    .sum()
    .sort_values('total_boardings', ascending=False)
)

per_route['pct_share'] = per_route['total_boardings'] / per_route['total_boardings'].sum()
per_route['cum_share'] = per_route['pct_share'].cumsum()

per_route.to_csv(
    OUTPUT_DIR / "cr_weekday_boardings_per_route_with_shares.csv", 
    index=False
)

# 6. Visualization
try:
    plt.figure(figsize=(10, 4))
    (
        per_route
        .set_index('route_id')['total_boardings']
        .head(20)
        .plot(kind='bar', color='purple')
    )
    plt.title(f"Top Commuter Rail Routes — {DAY_TYPE} Boardings")
    plt.ylabel("Total Boardings")
    plt.tight_layout()
    plt.show()
except Exception as e:
    print(f"Plotting skipped: {e}")