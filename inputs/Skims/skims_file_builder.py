#### Code V4 - going back to using original skim file as index guide to match taz-to-

import pandas as pd
import numpy as np
import openmatrix as omx
import json
import os
import time

class SkimFileBuilder:
    """
    A class to efficiently build a skim file by reading TAZ pairs from a base file,
    looking up values in OMX matrices using fast, full-matrix loading, and writing
    the results to a CSV file. The process is controlled by a JSON configuration file.
    """

    def __init__(self, config_path):
        """
        Initializes the SkimFileBuilder with a configuration file.

        Args:
            config_path (str): The file path for the JSON configuration.
        """
        print(f"Initializing builder with configuration: {config_path}")
        self.config_path = config_path
        self.config = self._load_config()
        self.df = None

    def _load_config(self):
        """Loads and validates the JSON configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            # Basic validation
            if not all(k in config for k in ['base_taz_pair_file', 'output_csv_path', 'omx_configs']):
                raise ValueError("Configuration file is missing 'base_taz_pair_file', 'output_csv_path', or 'omx_configs'.")
            print("Configuration loaded successfully.")
            return config
        except FileNotFoundError:
            print(f"ERROR: Configuration file not found at {self.config_path}")
            raise
        except json.JSONDecodeError:
            print(f"ERROR: Could not decode JSON from {self.config_path}")
            raise
        except ValueError as e:
            print(f"ERROR: {e}")
            raise

    def _load_or_create_dataframe(self):
        """
        Loads the output CSV if it exists, otherwise creates a new DataFrame
        from the base TAZ pair file.
        """
        output_path = self.config['output_csv_path']
        base_path = self.config['base_taz_pair_file']

        if os.path.exists(output_path):
            print(f"Found existing output file. Loading data from: {output_path}")
            # Use smaller dtypes to reduce memory usage
            self.df = pd.read_csv(output_path, header=None, dtype=np.float32)
            # Ensure TAZ columns are integers
            self.df[0] = self.df[0].astype(np.int32)
            self.df[1] = self.df[1].astype(np.int32)
        else:
            print(f"Output file not found. Creating new DataFrame from base file: {base_path}")
            try:
                # We only need the first two columns (TAZ from/to)
                self.df = pd.read_csv(base_path, header=None, usecols=[0, 1], dtype=np.int32)
            except FileNotFoundError:
                print(f"ERROR: The base TAZ pair file was not found at {base_path}")
                raise
            except Exception as e:
                print(f"ERROR: Could not read the base TAZ file: {e}")
                raise

    def _ensure_columns_exist(self, max_col_index):
        """
        Ensures the DataFrame has enough columns to write to, adding new
        columns with a memory-efficient float type if necessary.
        """
        current_max_index = self.df.shape[1] - 1
        if max_col_index > current_max_index:
            print(f"Expanding DataFrame columns up to index {max_col_index}.")
            for i in range(current_max_index + 1, max_col_index + 1):
                self.df[i] = np.nan
            # Cast new columns to a memory-efficient float type
            self.df = self.df.astype({i: np.float32 for i in range(current_max_index + 1, max_col_index + 1)})


    def process_skims(self):
        """
        Main processing function. It iterates through the OMX configurations,
        reads matrices efficiently, and populates the DataFrame.
        """
        print("\n--- Starting Efficient Skim Processing ---")
        start_time = time.time()
        self._load_or_create_dataframe()

        if self.df is None:
            print("ERROR: DataFrame could not be loaded. Aborting process.")
            return

        # Get the origin and destination TAZs once as NumPy arrays for speed.
        # TAZs in the file are 1-indexed, so we subtract 1 for 0-based lookup.
        try:
            orig_indexes = self.df[0].values - 1
            dest_indexes = self.df[1].values - 1
        except (KeyError, IndexError):
            print("ERROR: DataFrame does not have the required origin/destination TAZ columns (0 and 1).")
            return

        # Iterate over each OMX file configuration
        for omx_config in self.config['omx_configs']:
            omx_path = omx_config['omx_file_path']
            mappings = omx_config['matrix_to_column_index']
            print(f"\nProcessing OMX file: {omx_path}")

            try:
                with omx.open_file(omx_path, 'r') as omx_file:
                    max_col_needed = max(mappings.values())
                    self._ensure_columns_exist(max_col_needed)

                    # Process each matrix mapping for the current OMX file
                    for matrix_name, col_index in mappings.items():
                        print(f"  - Mapping matrix '{matrix_name}' to column {col_index}...", end="", flush=True)
                        try:
                            # --- EFFICIENT BATCH LOGIC ---
                            # 1. Read the ENTIRE matrix into a NumPy array.
                            matrix_data = omx_file[matrix_name].read()

                            # 2. Use advanced indexing to get all values in ONE operation.
                            values = matrix_data[orig_indexes, dest_indexes]

                            # 3. Assign the values to the DataFrame column.
                            self.df[col_index] = np.round(values.astype(np.float32), 2)
                            # self.df[col_index] = np.round(values, 2)

                            # --- END OF EFFICIENT LOGIC ---
                            print(" Done.")

                        except KeyError:
                            print(f"\n    WARNING: Matrix '{matrix_name}' not found in {omx_path}. Skipping.")
                        except Exception as e:
                            print(f"\n    ERROR: An unexpected error occurred while processing matrix '{matrix_name}': {e}")

            except FileNotFoundError:
                print(f"  WARNING: OMX file not found at {omx_path}. Skipping this configuration.")
                continue
            except Exception as e:
                print(f"  ERROR: Could not open or process OMX file {omx_path}: {e}")
                continue
        
        end_time = time.time()
        print(f"\n--- Skim Processing Complete in {end_time - start_time:.2f} seconds ---")

    def save_output(self):
        """Saves the processed DataFrame to the output CSV file."""
        if self.df is not None:
            output_path = self.config['output_csv_path']
            print(f"\nSaving processed data to: {output_path}")
            start_time = time.time()
            # The output file can be large, so this step may take time.
            self.df.to_csv(output_path, index=False, header=False) #, float_format='%.2f')
            end_time = time.time()
            print(f"Save complete in {end_time - start_time:.2f} seconds.")
        else:
            print("WARNING: DataFrame is not available to save. Did processing fail?")

    def verify_output(self):
        """Prints the head and tail of the DataFrame for verification."""
        if self.df is not None:
            num_rows = self.config.get('data_display_row_count', 5)
            print(f"\n--- Verification: First {num_rows} rows ---")
            print(self.df.head(num_rows).to_string())
            print(f"\n--- Verification: Last {num_rows} rows ---")
            print(self.df.tail(num_rows).to_string())
        else:
            print("WARNING: DataFrame is not available for verification.")




# #### Code V3
# import pandas as pd
# import numpy as np
# import openmatrix as omx
# import json
# import os
# import itertools
# import time # Import time for performance measurement

# class SkimFileBuilder:
#     """
#     An efficient class to build a skim file by generating all TAZ pairs,
#     loading full OMX matrices into memory, and writing the results to a CSV file.
#     """

#     def __init__(self, config_path):
#         """
#         Initializes the SkimFileBuilder with a configuration file.

#         Args:
#             config_path (str): The file path for the JSON configuration.
#         """
#         print(f"Initializing builder with configuration: {config_path}")
#         self.config_path = config_path
#         self.config = self._load_config()
#         self.df = None

#     def _load_config(self):
#         """Loads and validates the JSON configuration file."""
#         try:
#             with open(self.config_path, 'r') as f:
#                 config = json.load(f)
#             if not all(k in config for k in ['output_csv_path', 'omx_configs']):
#                 raise ValueError("Configuration file must contain 'output_csv_path' and 'omx_configs' keys.")
#             print("Configuration loaded successfully.")
#             return config
#         except Exception as e:
#             print(f"ERROR loading config: {e}")
#             raise

#     def _get_taz_count(self):
#         """Determines the number of TAZs from config or the first OMX file."""
#         if self.config.get('number_of_tazs'):
#             count = int(self.config['number_of_tazs'])
#             print(f"Using TAZ count provided in configuration: {count}")
#             return count

#         print("Determining TAZ count from the first OMX file...")
#         if not self.config['omx_configs']:
#             raise ValueError("Configuration has no 'omx_configs' to determine TAZ count from.")
        
#         first_omx_path = self.config['omx_configs'][0]['omx_file_path']
#         try:
#             with omx.open_file(first_omx_path, 'r') as f:
#                 taz_count = f.shape()[0]
#                 print(f"  -> Determined TAZ count: {taz_count}")
#                 return taz_count
#         except Exception as e:
#             print(f"ERROR determining TAZ count from {first_omx_path}: {e}")
#             raise

#     def _create_base_dataframe(self):
#         """Creates a new DataFrame containing all possible TAZ pairs."""
#         num_tazs = self._get_taz_count()
#         print(f"\nGenerating all TAZ pairs for {num_tazs} zones...")
        
#         # Use smaller integer types to save memory
#         taz_dtype = np.int16 if num_tazs < 32767 else np.int32
        
#         taz_range = range(1, num_tazs + 1)
#         pairs = list(itertools.product(taz_range, repeat=2))
        
#         self.df = pd.DataFrame(pairs, columns=[0, 1], dtype=taz_dtype)
#         print(f"Successfully created a base DataFrame with {len(self.df):,} TAZ pairs.")

#     def _ensure_columns_exist(self, max_col_index):
#         """Ensures the DataFrame has enough columns."""
#         current_max_index = self.df.shape[1] - 1
#         if max_col_index > current_max_index:
#             for i in range(current_max_index + 1, max_col_index + 1):
#                 # Initialize with a smaller float type to save memory
#                 self.df[i] = np.nan
#             self.df = self.df.astype({i: np.float32 for i in range(current_max_index + 1, max_col_index + 1)})


#     def process_skims(self):
#         """
#         Main processing function. Uses EFFICIENT full-matrix loading.
#         """
#         print("\n--- Starting Efficient Skim Processing ---")
#         start_time = time.time()
#         self._create_base_dataframe()

#         # Get origin/destination indexes once. These are NumPy arrays.
#         orig_indexes = self.df[0].values - 1
#         dest_indexes = self.df[1].values - 1

#         for omx_config in self.config['omx_configs']:
#             omx_path = omx_config['omx_file_path']
#             mappings = omx_config['matrix_to_column_index']
#             print(f"\nProcessing OMX file: {omx_path}")

#             try:
#                 with omx.open_file(omx_path, 'r') as omx_file:
#                     max_col_needed = max(mappings.values())
#                     self._ensure_columns_exist(max_col_needed)

#                     for matrix_name, col_index in mappings.items():
#                         print(f"  - Mapping matrix '{matrix_name}' to column {col_index}...", end="")
                        
#                         try:
#                             # === EFFICIENT LOGIC START ===
#                             # 1. Read the ENTIRE matrix into a NumPy array
#                             matrix_data = omx_file[matrix_name].read()

#                             # 2. Use advanced indexing to get all values in ONE operation
#                             values = matrix_data[orig_indexes, dest_indexes]
                            
#                             # 3. Assign the values to the DataFrame column
#                             self.df[col_index] = np.round(values.astype(np.float32), 2)
#                             # === EFFICIENT LOGIC END ===
                            
#                             print(" Done.")
                            
#                         except KeyError:
#                             print(f"\n    WARNING: Matrix '{matrix_name}' not found. Skipping.")
#                         except Exception as e:
#                             print(f"\n    ERROR on matrix '{matrix_name}': {e}")

#             except FileNotFoundError:
#                 print(f"  WARNING: OMX file not found at {omx_path}. Skipping.")
#                 continue
#             except Exception as e:
#                 print(f"  ERROR processing OMX file {omx_path}: {e}")
#                 continue
        
#         end_time = time.time()
#         print(f"\n--- Skim Processing Complete in {end_time - start_time:.2f} seconds ---")

#     def save_output(self):
#         """Saves the processed DataFrame to the output CSV file."""
#         if self.df is not None:
#             output_path = self.config['output_csv_path']
#             print(f"\nSaving processed data to: {output_path}")
#             start_time = time.time()
#             self.df.to_csv(output_path, index=False, header=False, float_format='%.2f')
#             end_time = time.time()
#             print(f"Save complete in {end_time - start_time:.2f} seconds.")
#         else:
#             print("WARNING: DataFrame is not available to save.")

#     # verify_output method remains the same...
#     def verify_output(self):
#         """Prints the head and tail of the DataFrame for verification."""
#         if self.df is not None:
#             num_rows = self.config.get('data_display_row_count', 5)
#             print(f"\n--- Verification: First {num_rows} rows ---")
#             print(self.df.head(num_rows).to_string())
#             print(f"\n--- Verification: Last {num_rows} rows ---")
#             print(self.df.tail(num_rows).to_string())
#         else:
#             print("WARNING: DataFrame is not available for verification.")

# if __name__ == '__main__':
#     CONFIG_FILE = 'skim_file_builder_configuration.json'
#     try:
#         builder = SkimFileBuilder(config_path=CONFIG_FILE)
#         builder.process_skims()
#         builder.save_output()
#         builder.verify_output()
#     except Exception as e:
#         print(f"\nA critical error occurred: {e}")


#### Code V2

# import pandas as pd
# import numpy as np
# import openmatrix as omx
# import json
# import os
# import itertools

# class SkimFileBuilder:
#     """
#     A class to build a skim file by generating all TAZ pairs based on matrix
#     dimensions, looking up values in OMX matrices, and writing the results
#     to a CSV file. The process is controlled by a JSON configuration file.
#     """

#     def __init__(self, config_path):
#         """
#         Initializes the SkimFileBuilder with a configuration file.

#         Args:
#             config_path (str): The file path for the JSON configuration.
#         """
#         print(f"Initializing builder with configuration: {config_path}")
#         self.config_path = config_path
#         self.config = self._load_config()
#         self.df = None

#     def _load_config(self):
#         """Loads and validates the JSON configuration file."""
#         try:
#             with open(self.config_path, 'r') as f:
#                 config = json.load(f)
#             # Basic validation
#             if not all(k in config for k in ['output_csv_path', 'omx_configs']):
#                 raise ValueError("Configuration file must contain 'output_csv_path' and 'omx_configs' keys.")
#             print("Configuration loaded successfully.")
#             return config
#         except FileNotFoundError:
#             print(f"ERROR: Configuration file not found at {self.config_path}")
#             raise
#         except json.JSONDecodeError:
#             print(f"ERROR: Could not decode JSON from {self.config_path}")
#             raise
#         except ValueError as e:
#             print(f"ERROR: {e}")
#             raise

#     def _get_taz_count(self):
#         """
#         Determines the number of TAZs.
#         It first checks for a manual override in the config ('number_of_tazs').
#         If not found, it infers the count from the first specified OMX file.
#         """
#         # 1. Check for manual override in the config
#         if self.config.get('number_of_tazs'):
#             count = int(self.config['number_of_tazs'])
#             print(f"Using TAZ count provided in configuration: {count}")
#             return count

#         # 2. Infer from the first OMX file if no override is present
#         print("No 'number_of_tazs' key found in config. Determining TAZ count from OMX file...")
#         if not self.config['omx_configs']:
#             raise ValueError("Configuration has no 'omx_configs' to determine TAZ count from.")
        
#         first_omx_path = self.config['omx_configs'][0]['omx_file_path']
#         print(f"Reading first OMX file: {first_omx_path}")
        
#         try:
#             with omx.open_file(first_omx_path, 'r') as f:
#                 matrices = f.list_matrices()
#                 if not matrices:
#                     raise ValueError(f"No matrices found in OMX file: {first_omx_path}")
#                 # Get shape from the first matrix
#                 shape = f[matrices[0]].shape
#                 if len(shape) != 2 or shape[0] != shape[1]:
#                     print(f"  -> WARNING: Matrix '{matrices[0]}' is not square (shape: {shape}). Using the first dimension for TAZ count.")
#                 taz_count = shape[0]
#                 print(f"  -> Successfully determined TAZ count: {taz_count}")
#                 return taz_count
#         except FileNotFoundError:
#             print(f"ERROR: The OMX file specified for TAZ count detection was not found at {first_omx_path}")
#             raise
#         except Exception as e:
#             print(f"ERROR: Could not determine TAZ count from {first_omx_path}: {e}")
#             raise

#     def _create_base_dataframe(self):
#         """
#         Creates a new DataFrame containing all possible TAZ pairs.
#         """
#         num_tazs = self._get_taz_count()
#         if not num_tazs or num_tazs <= 0:
#             raise ValueError("Could not determine a valid number of TAZs.")
        
#         print(f"\nGenerating all TAZ pairs for {num_tazs} zones. This will create {num_tazs*num_tazs:,} rows.")
#         # Generate 1-based TAZ pairs (1,1), (1,2), ... (N,N)
#         taz_range = range(1, num_tazs + 1)
#         pairs = list(itertools.product(taz_range, repeat=2))
        
#         self.df = pd.DataFrame(pairs, columns=[0, 1])
#         print(f"Successfully created a base DataFrame with {len(self.df):,} TAZ pairs.")

#     def _ensure_columns_exist(self, max_col_index):
#         """
#         Ensures the DataFrame has enough columns to write to, adding new
#         columns with NaN values if necessary.
#         """
#         current_max_index = self.df.shape[1] - 1
#         if max_col_index > current_max_index:
#             print(f"Expanding DataFrame columns up to index {max_col_index}.")
#             for i in range(current_max_index + 1, max_col_index + 1):
#                 self.df[i] = np.nan

#     def process_skims(self):
#         """
#         Main processing function. It generates the TAZ pairs, iterates 
#         through the OMX configurations, reads matrices, and populates the DataFrame.
#         """
#         print("\n--- Starting Skim Processing ---")
#         self._create_base_dataframe()

#         # TAZs in the file are 1-indexed, so subtract 1 for 0-based lookup.
#         orig_indexes = self.df[0].values - 1
#         dest_indexes = self.df[1].values - 1

#         # Iterate over each OMX file configuration
#         for omx_config in self.config['omx_configs']:
#             omx_path = omx_config['omx_file_path']
#             mappings = omx_config['matrix_to_column_index']
#             print(f"\nProcessing OMX file: {omx_path}")

#             try:
#                 with omx.open_file(omx_path, 'r') as omx_file:
#                     # Ensure all required columns exist before processing
#                     max_col_needed = max(mappings.values())
#                     self._ensure_columns_exist(max_col_needed)

#                     # Process each matrix mapping for the current OMX file
#                     for matrix_name, col_index in mappings.items():
#                         print(f"  - Mapping matrix '{matrix_name}' to column index {col_index}")
#                         try:
#                             matrix = omx_file[matrix_name]
#                             values = matrix[orig_indexes, dest_indexes]
#                             self.df[col_index] = np.round(values, 2)
#                         except KeyError:
#                             print(f"    WARNING: Matrix '{matrix_name}' not found in {omx_path}. Skipping.")
#                         except Exception as e:
#                             print(f"    ERROR: Unexpected error on matrix '{matrix_name}': {e}")

#             except FileNotFoundError:
#                 print(f"  WARNING: OMX file not found at {omx_path}. Skipping this configuration.")
#                 continue
#             except Exception as e:
#                 print(f"  ERROR: Could not open or process OMX file {omx_path}: {e}")
#                 continue
        
#         print("\n--- Skim Processing Complete ---")

#     def save_output(self):
#         """Saves the processed DataFrame to the output CSV file."""
#         if self.df is not None:
#             output_path = self.config['output_csv_path']
#             print(f"\nSaving processed data to: {output_path}")
#             # The output file can be large, so this step may take time.
#             self.df.to_csv(output_path, index=False, header=False, float_format='%.2f')
#             print("Save complete.")
#         else:
#             print("WARNING: DataFrame is not available to save. Did processing fail?")

#     def verify_output(self):
#         """Prints the head and tail of the DataFrame for verification."""
#         if self.df is not None:
#             num_rows = self.config.get('data_display_row_count', 5)
#             print(f"\n--- Verification: First {num_rows} rows ---")
#             print(self.df.head(num_rows).to_string())
#             print(f"\n--- Verification: Last {num_rows} rows ---")
#             print(self.df.tail(num_rows).to_string())
#         else:
#             print("WARNING: DataFrame is not available for verification.")

# if __name__ == '__main__':
#     # --- How to use the class ---
#     # 1. Define the path to your configuration file.
#     CONFIG_FILE = 'skim_file_builder_configuration.json'

#     # 2. Create an instance of the builder and run the process.
#     try:
#         builder = SkimFileBuilder(config_path=CONFIG_FILE)
#         builder.process_skims()
#         builder.save_output()
#         builder.verify_output()
#     except Exception as e:
#         print(f"\nA critical error occurred during the build process: {e}")


#### Code V1
# import pandas as pd
# import numpy as np
# import openmatrix as omx
# import json
# import os

# class SkimFileBuilder:
#     """
#     A class to build a skim file by reading TAZ pairs, looking up values
#     in OMX matrices, and writing the results to a CSV file.
#     The entire process is controlled by a JSON configuration file.
#     """

#     def __init__(self, config_path):
#         """
#         Initializes the SkimFileBuilder with a configuration file.

#         Args:
#             config_path (str): The file path for the JSON configuration.
#         """
#         print(f"Initializing builder with configuration: {config_path}")
#         self.config_path = config_path
#         self.config = self._load_config()
#         self.df = None

#     def _load_config(self):
#         """Loads and validates the JSON configuration file."""
#         try:
#             with open(self.config_path, 'r') as f:
#                 config = json.load(f)
#             # Basic validation
#             if not all(k in config for k in ['base_taz_pair_file', 'output_csv_path', 'omx_configs']):
#                 raise ValueError("Configuration file is missing required keys.")
#             print("Configuration loaded successfully.")
#             return config
#         except FileNotFoundError:
#             print(f"ERROR: Configuration file not found at {self.config_path}")
#             raise
#         except json.JSONDecodeError:
#             print(f"ERROR: Could not decode JSON from {self.config_path}")
#             raise
#         except ValueError as e:
#             print(f"ERROR: {e}")
#             raise

#     def _load_or_create_dataframe(self):
#         """
#         Loads the output CSV if it exists, otherwise creates a new DataFrame
#         from the base TAZ pair file.
#         """
#         output_path = self.config['output_csv_path']
#         base_path = self.config['base_taz_pair_file']

#         if os.path.exists(output_path):
#             print(f"Found existing output file. Loading data from: {output_path}")
#             self.df = pd.read_csv(output_path, header=None)
#         else:
#             print(f"Output file not found. Creating new DataFrame from base file: {base_path}")
#             try:
#                 # We only need the first two columns (TAZ from/to)
#                 self.df = pd.read_csv(base_path, header=None, usecols=[0, 1])
#             except FileNotFoundError:
#                 print(f"ERROR: The base TAZ pair file was not found at {base_path}")
#                 raise
#             except Exception as e:
#                 print(f"ERROR: Could not read the base TAZ file: {e}")
#                 raise

#     def _ensure_columns_exist(self, max_col_index):
#         """
#         Ensures the DataFrame has enough columns to write to, adding new
#         columns with NaN values if necessary.
#         """
#         current_max_index = self.df.shape[1] - 1
#         if max_col_index > current_max_index:
#             print(f"Expanding DataFrame columns up to index {max_col_index}.")
#             for i in range(current_max_index + 1, max_col_index + 1):
#                 self.df[i] = np.nan

#     def process_skims(self):
#         """
#         Main processing function. It iterates through the OMX configurations,
#         reads matrices, and populates the DataFrame.
#         """
#         print("\nStarting skim processing...")
#         self._load_or_create_dataframe()

#         # Get the origin and destination TAZs once.
#         # TAZs in the file are 1-indexed, so we subtract 1 for 0-based lookup.
#         try:
#             orig_indexes = self.df[0].astype(int).values - 1
#             dest_indexes = self.df[1].astype(int).values - 1
#         except (KeyError, IndexError):
#             print("ERROR: DataFrame does not have the required origin/destination TAZ columns (0 and 1).")
#             return

#         # Iterate over each OMX file configuration
#         for omx_config in self.config['omx_configs']:
#             omx_path = omx_config['omx_file_path']
#             mappings = omx_config['matrix_to_column_index']
#             print(f"\nProcessing OMX file: {omx_path}")

#             try:
#                 with omx.open_file(omx_path, 'r') as omx_file:
#                     print(f"  Available matrices: {omx_file.list_matrices()}")
                    
#                     # Check if all required columns can be accommodated
#                     max_col_needed = max(mappings.values())
#                     self._ensure_columns_exist(max_col_needed)

#                     # Process each matrix mapping for the current OMX file
#                     for matrix_name, col_index in mappings.items():
#                         print(f"  - Mapping matrix '{matrix_name}' to column index {col_index}")
#                         try:
#                             # Extract the matrix data
#                             matrix = omx_file[matrix_name]
#                             # Look up values using the TAZ indexes
#                             values = matrix[orig_indexes, dest_indexes]
#                             # Round and assign to the DataFrame
#                             self.df[col_index] = np.round(values, 2)
#                         except KeyError:
#                             print(f"    WARNING: Matrix '{matrix_name}' not found in {omx_path}. Skipping.")
#                         except Exception as e:
#                             print(f"    ERROR: An unexpected error occurred while processing matrix '{matrix_name}': {e}")

#             except FileNotFoundError:
#                 print(f"  WARNING: OMX file not found at {omx_path}. Skipping this configuration.")
#                 continue
#             except Exception as e:
#                 print(f"  ERROR: Could not open or process OMX file {omx_path}: {e}")
#                 continue
        
#         print("\nSkim processing complete.")

#     def save_output(self):
#         """Saves the processed DataFrame to the output CSV file."""
#         if self.df is not None:
#             output_path = self.config['output_csv_path']
#             print(f"\nSaving processed data to: {output_path}")
#             self.df.to_csv(output_path, index=False, header=False)
#             print("Save complete.")
#         else:
#             print("WARNING: DataFrame is not available to save. Did processing fail?")

#     def verify_output(self):
#         """Prints the head and tail of the DataFrame for verification."""
#         if self.df is not None:
#             num_rows = self.config.get('data_display_row_count', 5)
#             print(f"\n--- Verification: First {num_rows} rows ---")
#             print(self.df.head(num_rows).to_string())
#             print(f"\n--- Verification: Last {num_rows} rows ---")
#             print(self.df.tail(num_rows).to_string())
#         else:
#             print("WARNING: DataFrame is not available for verification.")

# if __name__ == '__main__':
#     # --- How to use the class ---
#     # 1. Define the path to your configuration file.
#     CONFIG_FILE = 'skim_file_builder_configuration.json'

#     # 2. Create an instance of the builder.
#     try:
#         builder = SkimFileBuilder(config_path=CONFIG_FILE)

#         # 3. Run the process.
#         builder.process_skims()

#         # 4. Save the final output.
#         builder.save_output()

#         # 5. Verify the results.
#         builder.verify_output()

#     except Exception as e:
#         print(f"\nA critical error occurred during the build process: {e}")
