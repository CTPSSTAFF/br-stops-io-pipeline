from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- Configuration ---
INPUT_DIR = Path("./20251216_Raw_RouteCounts")
OUTPUT_DIR = Path("./20251216_Processed_RouteCounts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = INPUT_DIR / "MBTA_Ferry_Daily_Ridership_by_Trip%2C_Route%2C_and_Stop.csv"

# Filter Constants
START_DATE = '2024-09-01'
END_DATE = '2024-10-31'
EXCLUDE_TRIP_FREQ = ['Sat', 'Unknown']
FERRY_TARGET_SUM = 5_411

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

# 1. Load and Date Filter
df = pd.read_csv(DATA_FILE, low_memory=False)
df['service_date'] = pd.to_datetime(df['service_date'], errors='coerce')

df_filtered = df[
    (df['service_date'] >= START_DATE) & 
    (df['service_date'] <= END_DATE)
].copy()

print(f"Loaded {len(df):,} rows. Filtered to {len(df_filtered):,} rows ({START_DATE} to {END_DATE}).")

# 2. Clean and Export Seasonal Data
# Remove weekend/unknown frequencies for weekday analysis
df_weekday = df_filtered[~df_filtered['trip_freq'].isin(EXCLUDE_TRIP_FREQ)].copy()
df_weekday.to_csv(OUTPUT_DIR / "MBTA_Ferry_Ridership_Fall2024.csv", index=False)

# 3. Aggregate Boardings (pax_on)
agg_boardings = (
    df_weekday.groupby(['route_id'], as_index=False)['pax_on']
    .sum()
    .rename(columns={'pax_on': 'total_boardings'})
    .sort_values(['route_id', 'total_boardings'], ascending=[True, False])
)

# 4. Scale to Control Totals
agg_ferry_scaled, ferry_scale_factor = scale_to_target(
    agg_boardings, "total_boardings", FERRY_TARGET_SUM
)

print(f"Ferry total (raw): {agg_boardings['total_boardings'].sum():,.1f}")
print(f"Scale factor applied: {ferry_scale_factor:.6f}")
print(f"Scaled sum: {agg_ferry_scaled['total_boardings'].sum():,.1f}")

# Save scaled aggregate
agg_ferry_scaled.to_csv(
    OUTPUT_DIR / "ferry_route_weekday_boardings_aggregate_scaled.csv", 
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

# Calculate shares for ranking
per_route = (
    agg_boardings
    .groupby('route_id', as_index=False)['total_boardings']
    .sum()
    .sort_values('total_boardings', ascending=False)
)

per_route['pct_share'] = per_route['total_boardings'] / per_route['total_boardings'].sum()
per_route['cum_share'] = per_route['pct_share'].cumsum()

per_route.to_csv(
    OUTPUT_DIR / "ferry_weekday_boardings_per_route_with_shares.csv", 
    index=False
)

# 6. Visualization
try:
    plt.figure(figsize=(10, 4))
    (
        per_route
        .set_index('route_id')['total_boardings']
        .plot(kind='bar', color='teal')
    )
    plt.title("Ferry Routes — Weekday Boardings (Fall 2024)")
    plt.ylabel("Total Boardings")
    plt.tight_layout()
    plt.show()
except Exception as e:
    print(f"Plotting skipped: {e}")