from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

def run_bus_processing(input_dir, input_filename, output_dir):
    """
    Processes MBTA Bus ridership data.
    Splits Silver Line and Regular Bus data, scales them to different targets,
    and produces aggregate statistics.
    
    Args:
        input_dir (Path): Directory containing input CSVs.
        input_filename (str): Name of the Bus CSV file.
        output_dir (Path): Directory where output files will be saved.
    """
    # 1. Setup Paths
    input_path = input_dir / input_filename
    output_dir = Path(output_dir)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Load Data
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path.resolve()}")

    print(f"Reading Bus data from: {input_path}")
    df = pd.read_csv(input_path, low_memory=False)
    print(f"Loaded {len(df):,} rows and {len(df.columns):,} columns")

    # 3. Aggregate boardings by route_id and day_type_name
    # Note: Bus data uses 'boardings' (unlike CR which used 'average_ons')
    agg_boardings = (
        df.groupby(['route_id', 'day_type_name'], as_index=False)['boardings']
          .sum()
          .rename(columns={'boardings': 'total_boardings'})
    )

    # Sort for easier inspection (highest totals first)
    agg_boardings = agg_boardings.sort_values(['route_id', 'total_boardings'], ascending=[True, False])

    # Filter for Weekday only
    agg_boardings = agg_boardings[agg_boardings['day_type_name'] == 'weekday']

    # 4. Split Silver Line vs Regular Bus
    # Hardcoded IDs from logic
    silver_ids = ['741', '742', '743', '751', '749', '746']

    agg_boarding_silver_line_bus = agg_boardings[agg_boardings['route_id'].isin(silver_ids)].copy()
    agg_boarding_bus = agg_boardings[~agg_boardings['route_id'].isin(silver_ids)].copy()

    # Sanity info
    print("\n--- Split Validation ---")
    print("Silver-line route_ids:", silver_ids)
    print(f"Silver Line: {len(agg_boarding_silver_line_bus)} routes, total_boardings = {agg_boarding_silver_line_bus['total_boardings'].sum():,.1f}")
    print(f"Regular Bus: {len(agg_boarding_bus)} routes, total_boardings = {agg_boarding_bus['total_boardings'].sum():,.1f}")
    
    # Validation assertions
    assert len(agg_boardings) == len(agg_boarding_bus) + len(agg_boarding_silver_line_bus)
    assert abs(agg_boardings['total_boardings'].sum() - (agg_boarding_bus['total_boardings'].sum() + agg_boarding_silver_line_bus['total_boardings'].sum())) < 1e-6

    # 5. Scale Regular Bus Data
    # Target: 299,374
    bus_boardings_sum = agg_boarding_bus['total_boardings'].sum()
    bus_target_sum = 299_374
    
    if bus_boardings_sum != 0:
        bus_scale_factor = bus_target_sum / bus_boardings_sum
    else:
        bus_scale_factor = 0

    agg_bus_boardings_scaled = agg_boarding_bus.copy()
    agg_bus_boardings_scaled['total_boardings'] = agg_bus_boardings_scaled['total_boardings'] * bus_scale_factor

    print(f"\nRegular Bus Scaled sum: {agg_bus_boardings_scaled['total_boardings'].sum():,.1f}")
    agg_bus_boardings_scaled.to_csv(output_dir / "agg_bus_boardings_scaled.csv", index=False)

    # 6. Scale Silver Line Data
    # Target: 33,236
    sl_boardings_sum = agg_boarding_silver_line_bus['total_boardings'].sum()
    sl_target_sum = 33_236
    
    if sl_boardings_sum != 0:
        sl_scale_factor = sl_target_sum / sl_boardings_sum
    else:
        sl_scale_factor = 0

    agg_sl_boardings_scaled = agg_boarding_silver_line_bus.copy()
    agg_sl_boardings_scaled['total_boardings'] = agg_sl_boardings_scaled['total_boardings'] * sl_scale_factor

    print(f"Silver Line Scaled sum: {agg_sl_boardings_scaled['total_boardings'].sum():,.1f}")
    agg_sl_boardings_scaled.to_csv(output_dir / "agg_sl_boardings_scaled.csv", index=False)

    # 7. Aggregate Statistics (On the combined, unscaled weekday data)
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
    print("\n--- Statistics (Combined Unscaled Weekday) ---")
    print(agg_stats)

    # 8. Re-aggregate by route_id for Ranking
    per_route = agg_boardings.groupby('route_id', as_index=False)['total_boardings'].sum()
    per_route = per_route.sort_values('total_boardings', ascending=False)

    print("\nTop 10 routes by weekday total_boardings:")
    print(per_route.head(10))

    # Add percent and cumulative share
    per_route['pct_share'] = per_route['total_boardings'] / per_route['total_boardings'].sum()
    per_route['cum_share'] = per_route['pct_share'].cumsum()
    
    per_route.to_csv(output_dir / "weekday_boardings_per_route_with_shares.csv", index=False)

    # 9. Generate Plot
    try:
        plt.figure(figsize=(10, 4))
        per_route.set_index('route_id')['total_boardings'].head(20).plot(
            kind='bar', title='Top 20 Bus Routes — Weekday Total Boardings'
        )
        plt.ylabel('total_boardings')
        plt.tight_layout()
        
        plot_path = output_dir / "top_20_routes_plot.png"
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved plot to: {plot_path}")
        
    except Exception as e:
        print(f"Could not generate plot: {e}")

    print("Bus processing complete.\n")