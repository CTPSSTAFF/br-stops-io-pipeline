STOPS Skims reads in "STOPS_PATH_Auto_Skim.csv" by columns and column ordering.

the configuration json file indicates the description of each of the column pairs for users (under _DESCRIPTION property)

To run, update the configuration json file and then 'run' the entire run builder python notebook.

The notebook relies on `skims_file_builder.py` for its logic.

Columns 0 and 1 are reserved for Origin and Destination TAZ.

Columns 2,3 are for Exist.

Columns 4,5 are for Open.

Columns 6,7 are for mid-range (10 Year) Forecasts.

Columns 8,9 are for long-range (20 Year) Forecasts.

Additional information is found in the FTA STOPS User Guide.
https://www.transit.dot.gov/sites/fta.dot.gov/files/2024-09/STOPS-User-Guide-v2-53-v.pdf
