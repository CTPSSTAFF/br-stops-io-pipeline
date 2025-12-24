```bash
(tdm23_env_1) PS D:\projects\br-stops-io-pipeline> python shop/evo1001.py --column-indices 7 8 9 --output nb_evo10.csv
Wrote 263 rows to nb_evo10.csv


python shop/evo901.py --column-indices 8 9 10 11 12

python shop/evosys.py --calibration-workbook "calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx" --evo9-csv evo9_01.csv --evo10-csv evo1001.csv --output evosys_estimates.csv


python shop/evo901.py --output ./tmp/evo901.csv
python shop/evo1001.py --output ./tmp/evo10.csv
python shop/evosys.py --evo9-csv ./tmp/evo901.csv --evo10-csv ./tmp/evo10.csv --output ./tmp/evosys.csv
```