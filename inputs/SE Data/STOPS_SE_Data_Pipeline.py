import pandas as pd
import os
import json
import argparse
from dbfread import DBF
import dbf
from pathlib import Path

def resolve_path(path_template, config):
    """
    Replaces placeholders in a path template with values from the config.
    This function can handle both {base_path} and {shared_drive_path}.
    """
    resolved_path = path_template.replace("{base_path}", config.get("base_path", ""))
    resolved_path = resolved_path.replace("{shared_drive_path}", config.get("shared_drive_path", ""))
    return resolved_path

def save_dataframe_to_dbf(df, output_path):
    """Saves a pandas DataFrame to a DBF file, handling column types and name lengths."""
    print(f"\nSaving final output to: {output_path}")
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"-> Created output directory: {output_dir}")
    try:
        df_for_dbf = df.copy()
        df_for_dbf.columns = [col[:10] for col in df.columns]
        field_specs = []
        for col, dtype in df_for_dbf.dtypes.items():
            if pd.api.types.is_integer_dtype(dtype): field_specs.append(f'{col} N(18, 0)')
            elif pd.api.types.is_float_dtype(dtype): field_specs.append(f'{col} F(19, 8)')
            elif pd.api.types.is_datetime64_any_dtype(dtype): field_specs.append(f'{col} D')
            elif pd.api.types.is_bool_dtype(dtype): field_specs.append(f'{col} L')
            else: field_specs.append(f'{col} C(254)')
        dbf_structure_string = '; '.join(field_specs)
        table = dbf.Table(output_path, dbf_structure_string, codepage='utf8')
        table.open(mode=dbf.READ_WRITE)
        for record in df_for_dbf.to_dict('records'):
            table.append(record)
        table.close()
        print(f"-> SUCCESS: Final DBF file with {len(df.columns)} columns saved.")
    except Exception as e:
        print(f"-> FATAL ERROR: Could not save the final DBF file: {e}")

def process_run_mode(run_config, config):
    """Main logic to process a run mode defined in the config."""

    master_dbf_path = resolve_path(run_config['baseline_dbf_file'], config)
    join_key_master = run_config['join_key_master']
    join_key_csv = run_config['join_key_csv']

    print(f"Loading base data from master DBF: {master_dbf_path}")
    try:
        df_merged = pd.DataFrame(iter(DBF(master_dbf_path, lowernames=True)))
        df_merged[join_key_master.lower()] = df_merged[join_key_master.lower()].astype(int)
        print(f"-> Loaded {len(df_merged)} base records.")
    except Exception as e:
        print(f"FATAL ERROR: Could not read the master DBF file: {e}")
        return

    for dataset in run_config['data_sets']:
        year = dataset['year']
        pop_col = dataset['pop_col_name']
        emp_col = dataset['emp_col_name']
        print(f"\n--- Processing data for year {year} ---")

        all_pop_dfs = []
        all_emp_dfs = []

        try:
            for source in dataset.get('sources', []):
                source_join_key = source.get('join_key_source', join_key_csv)

                # --- Process Employment Data ---
                emp_csv_path = resolve_path(source['emp_csv'], config)
                print(f"  -> Reading employment source: {os.path.basename(emp_csv_path)}")
                df_empl_source = pd.read_csv(emp_csv_path)
                emp_value_col = source['emp_value_col']
                df_empl_agg = df_empl_source[[source_join_key, emp_value_col]].copy()
                df_empl_agg.rename(columns={source_join_key: join_key_csv, emp_value_col: 'value'}, inplace=True)
                all_emp_dfs.append(df_empl_agg)

                # --- Process Population Data ---
                pop_csv_path = resolve_path(source['pop_csv'], config)
                print(f"  -> Reading population source: {os.path.basename(pop_csv_path)}")
                df_pop_source = pd.read_csv(pop_csv_path)
                if source['pop_agg_method'] == 'size':
                    if 'block_hid' in df_pop_source.columns and source_join_key not in df_pop_source.columns:
                        df_pop_source[source_join_key] = df_pop_source['block_hid'].astype(str).str.split('_').str[0].astype(int)
                    df_pop_agg = df_pop_source.groupby(source_join_key).size().reset_index(name='value')
                elif source['pop_agg_method'] == 'sum':
                    pop_value_col = source['pop_value_col']
                    df_pop_agg = df_pop_source.groupby(source_join_key)[pop_value_col].sum().reset_index()
                    df_pop_agg.rename(columns={pop_value_col: 'value'}, inplace=True)
                    
                df_pop_agg.rename(columns={source_join_key: join_key_csv}, inplace=True)
                all_pop_dfs.append(df_pop_agg)

            if not all_pop_dfs or not all_emp_dfs:
                print(f"-> WARNING: No data sources found or processed for year {year}. Skipping.")
                continue

            # --- Combine all sources for the year by summing ---
            df_pop_combined = pd.concat(all_pop_dfs)
            df_pop_total = df_pop_combined.groupby(join_key_csv)['value'].sum().reset_index(name=pop_col)

            df_emp_combined = pd.concat(all_emp_dfs)
            df_emp_total = df_emp_combined.groupby(join_key_csv)['value'].sum().reset_index(name=emp_col)
            
            df_year_data = pd.merge(df_emp_total, df_pop_total, on=join_key_csv, how='outer')
            print(f"-> Combined {len(dataset.get('sources', []))} sources into {len(df_year_data)} total records for {year}.")

            # --- Merge this year's combined data into the main DataFrame ---
            df_merged = pd.merge(df_merged, df_year_data, left_on=join_key_master.lower(), right_on=join_key_csv, how='left')
            df_merged.drop(columns=[join_key_csv], errors='ignore', inplace=True)
            df_merged[pop_col] = df_merged[pop_col].fillna(0).astype(int)
            df_merged[emp_col] = df_merged[emp_col].fillna(0).astype(float)
            print(f"-> Merged {year} data. DataFrame now has {len(df_merged.columns)} columns.")

        except (FileNotFoundError, KeyError) as e:
            print(f"-> WARNING: Could not process dataset for {year}. Skipping. Error: {e}")
            continue
            
    output_path = resolve_path(run_config['output_file'], config)
    save_dataframe_to_dbf(df_merged, output_path)

def main():
    """Parses command line arguments and initiates data processing."""
    parser = argparse.ArgumentParser(description="Process socio-economic data based on a JSON configuration.")
    parser.add_argument("--run_mode", required=True, help="The specific run mode (e.g., '2025AugRun') to execute from the config file.")
    args = parser.parse_args()
    
    config_file = 'pipeline_config.json'
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"FATAL ERROR: Configuration file '{config_file}' not found.")
        return
        
    run_mode_arg = args.run_mode
    all_runs = config.get("data_processing_runs", [])
    target_config = next((run for run in all_runs if run.get("run_mode") == run_mode_arg), None)

    if target_config:
        print(f"Starting process for run mode: '{run_mode_arg}'")
        process_run_mode(target_config, config)
    else:
        print(f"FATAL ERROR: Run mode '{run_mode_arg}' not found in '{config_file}'.")
        return
    
    print("\nScript finished.")

if __name__ == "__main__":
    main()