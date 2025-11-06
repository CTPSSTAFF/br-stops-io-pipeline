# Repository Guidelines

## Project Structure & Module Organization
- `calibration/` hosts the STOPS calibration workflow: `Main_Program.rmd` orchestrates `Extract_STOPS_Tables.R`, and Excel templates live beside the run-ready workbooks.
- `reports/Summary_Script/` contains the GTFS summary generator (`Summary.R` plus `Inputs/` scenario folders and `Outputs/` CSV deliverables); keep scenario-specific PRNs inside the matching subfolder.
- `inputs/` stores upstream pipelines: `MBTA GTFS/` notebooks, `Fares/` route split artifacts, `SE Data/` socio-economic processor, and `Skims/` skim builder assets.
- Generated artefacts should stay in their owning directory so relative references and Excel links remain valid.

## Build, Test, and Development Commands
- `Rscript -e "setwd('calibration'); rmarkdown::render('Main_Program.rmd')"` rebuilds `A1_Extracted_Tables.xlsx` and `A2_Formatted_Tables.xlsx`; confirm line 29 references the desired `Results.prn`.
- `Rscript reports/Summary_Script/Summary.R` refreshes the GTFS summary CSVs; adjust `Inputs/Input_Data&Parameters.xlsx` before execution.
- `python "inputs/SE Data/STOPS_SE_Data_Pipeline.py" --run_mode 2025AugRun` populates the DBF outputs defined in `pipeline_config.json`.
- Launch `inputs/Skims/[RUN ME] run_builder.ipynb` to regenerate skim CSVs; the notebook delegates to `skims_file_builder.py` and respects `skim_file_builder_configuration.json`.

## Coding Style & Naming Conventions
- R scripts follow tidyverse conventions: `<-` assignment, two-space indents, and snake_case variables; keep table IDs and sheet names literal to match STOPS exports.
- Python modules target PEP 8: four-space indents, descriptive class names (`SkimFileBuilder`), and f-strings for logging; prefer snake_case filenames for configs.
- Retain uppercase agency identifiers in folder names (`MBTA`, `CATA`) and avoid spaces in new filenames unless the dataset already ships that way.

## Testing Guidelines
- After each R run, open `A2_Formatted_Tables.xlsx` and the linked calibration template to spot check updated metrics and to ensure Excel formulas remain intact.
- Compare fresh GTFS summary CSVs against the previous run (`git diff reports/Summary_Script/Outputs/Route&StopLevel_Estimates_Build.csv`) before publishing.
- For socio-economic and skim builds, start with a single run_mode or matrix mapping, verify console warnings are resolved, and inspect row counts and key columns before full-scale processing.

## Commit & Pull Request Guidelines
- Prefix commit messages with the existing bracketed scope (`[dev]`, `[batch]`, `[admin]`), followed by an imperative summary (e.g., `[dev] refresh summary inputs`).
- Describe commands or notebooks executed in PR descriptions, list the scenario/run_mode, and attach screenshots when Excel formatting changes are involved.
- Ensure large generated outputs stay untracked; share review copies via attachments instead of Git history.
