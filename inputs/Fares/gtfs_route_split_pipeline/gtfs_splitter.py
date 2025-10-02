import sys
import os
import json
from gtfs_kit.feed import read_feed

def filter_gtfs(input_path):
    """
    Parses a GTFS feed, filters it based on a JSON config file,
    and saves the filtered feed to a new output folder.
    
    Args:
        input_path (str): The path to the subfolder containing
                          the config file.
    """
    # Define file paths
    config_file = os.path.join(input_path, 'Process_GTFS_Filter.json')

    # 1. Read the JSON configuration file
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Get folder names and routes to include/exclude from the config
        input_gtfs_folder_name = config.get('input_gtfs_folder_name', None)
        output_gtfs_folder_name = config.get('output_gtfs_folder_name', None)
        routes_to_include = config.get('routes_to_include', [])
        routes_to_exclude = config.get('routes_to_exclude', [])

        if not all([input_gtfs_folder_name, output_gtfs_folder_name]):
            print("Error: Missing 'input_gtfs_folder_name' or 'output_gtfs_folder_name' in the JSON config.")
            return

        # Ensure at least one filtering list is non-empty
        if not routes_to_include and not routes_to_exclude:
            print("Error: Both 'routes_to_include' and 'routes_to_exclude' are empty. No filtering will be applied.")
            return

    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{config_file}'")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in '{config_file}'.")
        return

    # Dynamically construct input and output folder paths
    input_gtfs_folder = os.path.join(input_path, input_gtfs_folder_name)
    output_gtfs_folder = os.path.join(input_path, output_gtfs_folder_name)

    # 2. Check if the input GTFS folder exists
    if not os.path.isdir(input_gtfs_folder):
        print(f"Error: Input GTFS folder not found at '{input_gtfs_folder}'")
        return

    # 3. Read and filter the GTFS feed
    print(f"Loading GTFS feed from: {input_gtfs_folder}")
    feed = read_feed(input_gtfs_folder, dist_units='m')

    print(f"Original feed has {len(feed.routes)} routes.")

    # Apply filtering based on which list is provided
    try:
        if routes_to_include:
            print(f"Including routes: {routes_to_include}")
            filtered_feed = feed.restrict_to_routes(routes_to_include)
        elif routes_to_exclude:
            print(f"Excluding routes: {routes_to_exclude}")
            all_route_ids = set(feed.routes['route_id'].unique())
            routes_to_keep = list(all_route_ids - set(routes_to_exclude))
            filtered_feed = feed.restrict_to_routes(routes_to_keep)
        else:
            print("No routes to filter. Keeping original feed.")
            filtered_feed = feed
    except Exception as e:
        print(f"An error occurred during filtering: {e}")
        return

    print(f"Filtered feed has {len(filtered_feed.routes)} routes.")

    # 4. Create the output directory if it doesn't exist
    if not os.path.exists(output_gtfs_folder):
        os.makedirs(output_gtfs_folder)
        print(f"Created output directory: {output_gtfs_folder}")
    
    # 5. Write the filtered feed to the output directory
    try:
        # v- CHANGE 2: Updated the write command
        filtered_feed.write(output_gtfs_folder)
        print(f"Successfully saved filtered GTFS feed to: {output_gtfs_folder}")
    except Exception as e:
        print(f"An error occurred while writing the filtered feed: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python GTFS_filter.py <path_to_subfolder>")
    else:
        path = sys.argv[1]
        filter_gtfs(path)