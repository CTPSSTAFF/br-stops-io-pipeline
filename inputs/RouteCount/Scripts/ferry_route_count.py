import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def run_ferry_processing(input_dir, input_filename, output_dir):
    """
    Processes MBTA Ferry ridership data.
    """
    print(f"--- Starting FERRY Processing ---")
    
    # Define Paths
    input_path = Path(input_dir) / input_filename
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path.resolve()}")

    # Load Data
    df = pd.read_csv(input_path, low_memory=False)

    # Filter Dates (Sept 1 - Oct 31, 2024)
    df['service_date'] = pd.to_datetime(df['service_date'], errors='coerce')
    start_date = '2024-09-01'
    end_date = '2024-10-31'
    
    df = df[(df['service_date'] >= start_date) & (df['service_date'] <= end_date)]
    
    # Filter Trip Frequency
    if 'trip_freq' in df.columns:
        df = df[~df['trip_freq'].isin(['Sat', 'Unknown'])]
        
    print(f"Loaded {len(df):,} rows after filtering.")

    # Aggregate
    # Mapping 'pax_on' -> 'total_boardings'
    agg_boardings = (
        df.groupby(['route_id'], as_index=False)['pax_on']
          .sum()
          .rename(columns={'pax_on': 'total_boardings'})
    )
    agg_boardings = agg_boardings.sort_values(['route_id', 'total_boardings'], ascending=[True, False])

    # Scale
    TARGET_SUM = 5_411
    current_sum = agg_boardings['total_boardings'].sum()
    scale_factor = TARGET_SUM / current_sum
    
    agg_total = agg_boardings.copy()
    
    print(f"Ferry Scale Factor: {scale_factor:.6f}")
    print(f"Scaled Sum: {agg_total['total_boardings'].sum():,.1f}")

    # Save Output
    agg_total.to_csv(output_path / "agg_ferry_boardings.csv", index=False)

    agg_scaled = agg_total.copy()
    agg_scaled['total_boardings'] *= scale_factor
    agg_scaled.to_csv(output_path / "agg_ferry_boardings_scaled.csv", index=False)

    # Generate Shares
    per_route = agg_total.groupby('route_id', as_index=False)['total_boardings'].sum()
    per_route = per_route.sort_values('total_boardings', ascending=False)
    per_route['pct_share'] = per_route['total_boardings'] / per_route['total_boardings'].sum()
    per_route['cum_share'] = per_route['pct_share'].cumsum()
    
    per_route.to_csv(output_path / "ferry_routes_with_shares.csv", index=False)
    print(f"--- FERRY Processing Complete ---\n")