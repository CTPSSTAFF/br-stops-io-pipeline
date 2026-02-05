import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def run_cr_processing(input_dir, input_filename, output_dir):
    """
    Processes MBTA Commuter Rail ridership data.
    Filters for Fall 2024, aggregates weekday ridership, and scales to target.
    """
    print(f"--- Starting Commuter Rail Processing ---")
    
    # Define Paths
    input_path = Path(input_dir) / input_filename
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path.resolve()}")

    # Load Data
    df = pd.read_csv(input_path, low_memory=False)
    print(f"Loaded {len(df):,} rows and {len(df.columns):,} columns")

    # Filter for Season
    SEASON_TARGET = 'Fall 2024'
    df = df[df['season'] == SEASON_TARGET].copy()
    print(f"Filtered for {SEASON_TARGET}: {len(df):,} rows remaining")
    
    # Save the filtered raw data
    df.to_csv(output_path / "MBTA_Commuter_Rail_Ridership_Fall2024.csv", index=False)

    # Constants
    CR_TARGET_SUM = 111_755
    DAY_TYPE = "weekday"

    # Aggregate by route and day_type
    # Note: Commuter Rail uses 'average_ons' instead of 'boardings'
    agg_boardings = (
        df.groupby(['route_id', 'day_type_name'], as_index=False)['average_ons']
          .sum()
          .rename(columns={'average_ons': 'total_boardings'})
    )
    
    # Sort for easier inspection
    agg_boardings = agg_boardings.sort_values(['route_id', 'total_boardings'], ascending=[True, False])

    # Filter for weekday
    agg_boardings = agg_boardings[agg_boardings['day_type_name'] == DAY_TYPE].copy()
    
    # Save unscaled aggregate
    agg_boardings.to_csv(output_path / "commuter_rail_route_weekday_boardings_aggregate.csv", index=False)

    # --- Scaling ---
    total_boardings_sum = agg_boardings['total_boardings'].sum()
    print(f"Sum of total_boardings (Raw): {total_boardings_sum:,.1f}")

    scale_factor = CR_TARGET_SUM / total_boardings_sum
    
    agg_boardings_scaled = agg_boardings.copy()
    agg_boardings_scaled['total_boardings'] = agg_boardings_scaled['total_boardings'] * scale_factor

    print(f"Scale Factor: {scale_factor:.6f}")
    print(f"Scaled sum: {agg_boardings_scaled['total_boardings'].sum():,.1f}")

    # Save Scaled Output
    agg_boardings_scaled.to_csv(output_path / "agg_commuter_rail_boardings_scaled.csv", index=False)

    # --- Stats & Shares ---
    tb = agg_boardings['total_boardings']
    agg_stats = pd.Series({
        'count': tb.count(), 'sum': tb.sum(), 'mean': tb.mean(),
        'median': tb.median(), 'std': tb.std(), 'min': tb.min(), 'max': tb.max()
    })
    print("\nAggregate statistics (Raw Weekday):")
    print(agg_stats)

    # Re-aggregate by route for shares
    per_route = (
        agg_boardings.groupby('route_id', as_index=False)['total_boardings']
        .sum()
        .sort_values('total_boardings', ascending=False)
    )

    print("\nTop 10 routes by weekday total_boardings:")
    print(per_route.head(10))

    print("\nBottom 10 routes by weekday total_boardings:")
    print(per_route.tail(10))

    per_route['pct_share'] = per_route['total_boardings'] / per_route['total_boardings'].sum()
    per_route['cum_share'] = per_route['pct_share'].cumsum()
    
    per_route.to_csv(output_path / "weekday_boardings_per_route_with_shares.csv", index=False)

    # # --- Plotting ---
    # try:
    #     plot_path = output_path / "top_20_routes_weekday_cr.png"
    #     (
    #         per_route.set_index('route_id')['total_boardings']
    #         .head(20)
    #         .plot(kind='bar', figsize=(10, 4), title='Top 20 Commuter Rail Routes — Weekday Boardings')
    #     )
    #     plt.ylabel('total_boardings')
    #     plt.tight_layout()
    #     plt.savefig(plot_path)
    #     plt.close()
    #     print(f"\nPlot saved to: {plot_path}")
    # except Exception as e:
    #     print(f"Could not generate plot: {e}")

    # print(f"--- Commuter Rail Processing Complete ---\n")