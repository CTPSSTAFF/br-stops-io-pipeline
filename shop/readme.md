Output data parse leverages existing data process from Boston_Regional_STOPS Calibration Report_2050.xlsx


"Boston_Regional_STOPS Calibration Report_2050.xlsx" is a copy of "Boston_Regional_STOPS Calibration Report_Template.xlsx", from which the aggregation and lookup logics are utilized.

There is also the excel "Boston_Regional_STOPS _mbta50_2045_2050_comparison_2024.xlsx" that is an updated excel from "Boston_Regional_STOPS Calibration Report_Template.xlsx"- the worksheet EvO10.01 from the 2024 excel file is updated to contain 2045 and 2050 in the respective worksheets in "Boston_Regional_STOPS _mbta50_2045_2050_comparison_2024.xlsx".

evo901.csv, ev1001.csv, evosys.csv, evosys_901.csv and evosys_1001.csv are generated from the data provided from the excel.

evo901.csv      - 2024
evo1001.csv     - 2024
evosys.csv      - 2024
evosys_901.csv  - 2024
evosys_1001.csv - 2024

TODO: Verify which year is used in what csv.

```bash
(tdm23_env_1) PS D:\projects\br-stops-io-pipeline> python shop/evo1001.py --column-indices 7 8 9 --output nb_evo10.csv
Wrote 263 rows to nb_evo10.csv


python shop/evo901.py --column-indices 8 9 10 11 12

# For the 2050 Network - reference to excel is used to incorporate new routes to the two tables in the calibration
# - Reads in calibration excel and writes out 901 and 1001
# - Calibration file does not have 2050 network so the script replicates the logic defined in the excel file
python shop/evosys.py --calibration-workbook "calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx" --evo9-csv evo9_01.csv --evo10-csv evo1001.csv --output evosys_estimates.csv

# 1 part
# - 2024 data brought in from prn file + Boston_Regional_STOPS Calibration Report_2050.xlsx format
python shop/evo901.py --output ./tmp/evo901.csv --column-indices 8 9 10 11 12

# 2 parts
# - 2024 data brought in from prn file + Boston_Regional_STOPS Calibration Report_2050.xlsx format
# - - lookup and aggregation logic also brought in
# - 2050 data brought in from Boston_Regional_STOPS _mbta50_2045_2050_comparison_2024.xlsx
python shop/evo1001.py --output ./tmp/evo101.csv --column-indices 8 9 10

python shop/evosys.py --evo9-csv ./tmp/evo901.csv --evo10-csv ./tmp/evo101.csv --output ./tmp/evosys.csv

python shop/evosys.py --evo9-csv ./tmp/evo901.csv  --output ./tmp/evosys_901.csv
python shop/evosys.py --evo10-csv ./tmp/evo101.csv  --output ./tmp/evosys_1001.csv
## create 1001 route-level summary by scenrio year(modify the prn URL in script)
python shop/prn1001.py
```