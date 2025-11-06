• Recommended Stack

  - R 4.4.1 — explicitly documented by the author in calibration/Extract_STOPS_Tables.R:8, and verified to work with the packages below.
  - RStudio 2025.05.0 Build 496 — matching the author’s note (calibration/Extract_STOPS_Tables.R:9) if you standardize on their IDE build.

  R Package Baseline

  - dplyr 1.1.4 — keeps superseded verbs like mutate_all/mutate_at used in calibration/Main_Program.rmd:15 without breaking changes, while remaining current.
  - data.table 1.15.4 — current CRAN release; loaded in calibration/Main_Program.rmd:16 and compatible with R 4.4.
  - foreign 0.8-86 — latest CRAN build for R 4.4; ensures read.dbf and other legacy readers available if invoked (calibration/Main_Program.rmd:17).
  - iotools 0.3.2 — provides dstrfw relied on throughout the extractor (calibration/Main_Program.rmd:18, calibration/Extract_STOPS_Tables.R:78).
  - janitor 2.2.0 — current stable; loaded in calibration/Main_Program.rmd:19 and backward compatible should name-cleaning utilities be used.
  - openxlsx 4.2.7.1 — ensures createWorkbook, addWorksheet, sheets, and writeData used in calibration/Main_Program.rmd:20 and calibration/Extract_STOPS_Tables.R:125 remain
    available.
  - stringr 1.5.1 — keeps str_squish/str_length used in both files stable (calibration/Main_Program.rmd:21, calibration/Extract_STOPS_Tables.R:83).
  - zeallot 0.1.0 — most recent CRAN release for the destructuring operator loaded in calibration/Main_Program.rmd:22.
  - scales 1.3.0 — required for scales::comma formatting (calibration/Main_Program.rmd:134).
  - knitr 1.48 and rmarkdown 2.27 — current releases supporting R 4.4, needed to render the R Markdown document (calibration/Main_Program.rmd:7).

  With this stack you’ll mirror the author’s documented runtime while staying on actively maintained CRAN builds that keep the scripted APIs stable. If you adopt alternative
  versions, stick with R ≥4.3 and package releases ≥2023 to retain the deprecated-but-used helpers.

### R Package Functionalities
  • Core Data

  - dplyr: tidy manipulation verbs for filtering, reshaping, and summarizing tabular data.
  - data.table: in-memory data frames optimized for fast aggregation and joins on large datasets.
  - foreign: legacy import/export utilities for SAS, SPSS, Stata, and DBF file formats.
  - iotools: streaming readers and fixed-width parsers suited to large STOPS report files.
  - janitor: quick-clean helpers for column names, tabulation, and spreadsheet-friendly summaries.
  - stringr: consistent string handling and regex wrappers used to trim and parse table text.
  - ggplot2: layered graphics for calibration diagnostics and report-ready visualizations.
  - readr: fast CSV readers for summary inputs and reporting parameters.
  - reshape2: matrix melt/cast utilities when reshaping STOPS outputs.
  - tidyverse: opinionated collection that keeps ggplot2/readr/tibble aligned when extending the workflow.

  Reporting & Output

  - openxlsx: pure-R tools to build, style, and write Excel workbooks without external dependencies.
  - scales: formatting helpers for numbers, percentages, and units in console or workbook output.
  - knitr: executes R chunks and embeds their results when rendering the R Markdown workflow.
  - rmarkdown: end-to-end document builder marrying markdown prose with executable R output.
  - htmltools: HTML widget utilities used for custom divs in the summary report.
  - kableExtra: table styling helpers that colorize and format kable outputs.
  - rmdformats: themed templates (e.g., readthedown) for the HTML summary deliverable.
  - zeallot: destructuring assignment syntax that unpacks list results into multiple variables.
  - progress: lightweight progress bars to track long-running loops in extractors.
  - rgdal: GDAL/PROJ bindings that allow shapefile reads for station and district layers.
  - leaflet & reactable: interactive map and table widgets embedded in the HTML report.

### Environment Setup (Windows, VSCode)
easy REPL(Read-Eval-Print Loop)
- Install R 4.4.1 from the official CRAN installer (download the `R-4.4.1-win.exe` bundle) so the interpreter is available system-wide at `C:\Program Files\R\R-4.4.1\bin\R.exe`. If you prefer to stay inside Anaconda, run `conda create --name stops-r -c conda-forge r-base=4.4.1` and rely on the environment-specific `R.exe` at `C:\Users\phoebe.AD\.conda\envs\stops-r\Scripts\R.exe`.
```bash
conda create --name stops-r -c conda-forge r-base=4.4.1
conda activate stops-r
```
- Add `C:\Program Files\R\R-4.4.1\bin` to your PATH (System Properties → Environment Variables) for access to `Rscript` inside every terminal. 
  For the conda-based install, either rely on `conda run -n stops-r Rscript` or add `C:\Users\phoebe.AD\.conda\envs\stops-r\Library\bin` to PATH.
```bash
conda activate stops-r
Rscript calibration\install_packages.R
---
The downloaded source packages are in
        'C:\Users\phoebe.AD\AppData\Local\Temp\RtmpEpBXOq\downloaded_packages'

```
- From a PowerShell or VSCode integrated terminal rooted at `D:\projects\br-stops-io-pipeline`, install the required dependencies with `Rscript calibration/install_packages.R`. (The script now covers both calibration and reporting needs: `dplyr`, `data.table`, `foreign`, `iotools`, `janitor`, `openxlsx`, `stringr`, `zeallot`, `scales`, `knitr`, `rmarkdown`, `future`, `future.apply`, `progress`, `readr`, `ggplot2`, `htmltools`, `kableExtra`, `leaflet`, `measurements`, `reactable`, `reshape2`, `rstudioapi`, `RColorBrewer`, `tidyverse`, `rmdformats`, and `remotes`; it also installs the archived `rgdal` from `reports/Summary_HTML_Report/rgdal.zip` and downloads `RStudioConsoleRender` from GitHub.) When using the conda interpreter, simply `conda activate stops-r` first and then run `Rscript`; this keeps Windows system utilities like `chcp` on your PATH.
- Install Pandoc once so `rmarkdown::render()` can run without RStudio. With conda this is `conda install -n stops-r -c conda-forge pandoc`; otherwise download the Windows installer from https://pandoc.org/installing.html and let it add itself to PATH.
- If the GitHub install of `RStudioConsoleRender` requests a compiler toolchain, install the matching Rtools build from https://cran.r-project.org/bin/windows/Rtools/ and rerun the package script.
```bash
conda install -n stops-r -c conda-forge pandoc
```
- In VSCode, install the “R” and “Code Runner” extensions, then set `"r.rterm.windows": "C:\\Program Files\\R\\R-4.4.1\\bin\\R.exe"` in your workspace settings to wire the REPL and inline execution to the same interpreter.
```bash
(stops-r) PS D:\projects\br-stops-io-pipeline> conda info --envs 
# conda environments:
#
base                     C:\ProgramData\Anaconda3
stops-r               *  C:\Users\phoebe.AD\.conda\envs\stops-r
---
 (e.g. C:\Users\phoebe.AD\.conda\envs\stops-r\Scripts\R.exe)
• Open VSCode, then:

  - Press Ctrl+, to open Settings, search for rterm → under the “R › Rterm: Windows” entry, choose “Edit in settings.json”.
  - Or go straight to the JSON: Ctrl+Shift+P → “Preferences: Open Settings (JSON)” → add a workspace or user setting like:

    "r.rterm.windows": "C:\\Users\\phoebe.AD\\.conda\\envs\\stops-r\\Scripts\\R.exe"
    Update the path if you’re using the CRAN install (e.g. C:\\Program Files\\R\\R-4.4.1\\bin\\R.exe).

```

- Ensure VSCode terminals default to PowerShell so the same PATH is used when running the pipelines. You can still reuse the base Python 3.9.13 or create a light `conda create --name stops-py python=3.9.13` environment for the socio-economic and skim scripts.

### Workflow & Testing (Windows, VSCode)
- Calibration tables: run `Rscript -e "setwd('calibration'); rmarkdown::render('Main_Program.rmd')"` from the VSCode terminal to regenerate `calibration/A1_Extracted_Tables.xlsx` and `calibration/A2_Formatted_Tables.xlsx`. After completion, inspect `A2_Formatted_Tables.xlsx` along with the linked calibration workbook to confirm metrics and formulas.
```bash
(stops-r) PS D:\projects\br-stops-io-pipeline> 
Rscript -e "setwd('reports/Summary_HTML_Report'); rmarkdown::render('Boston_Regional_STOPS_Summary_Report.rmd')"
Rscript -e "setwd('calibration'); rmarkdown::render('Main_Program.rmd')"
```
- GTFS summary: execute `Rscript reports/Summary_Script/Summary.R` using the same terminal. Compare the regenerated CSVs in `reports/Summary_Script/Outputs/` with `git diff reports/Summary_Script/Outputs/Route&StopLevel_Estimates_Build.csv`.
```bash
Rscript reports/Summary_Script/Summary.R
```
- HTML summary report: run `Rscript -e "setwd('reports/Summary_HTML_Report'); rmarkdown::render('Boston_Regional_STOPS_Summary_Report.rmd')"` to regenerate `reports/Summary_HTML_Report/BostonRegionalSTOPS_Summary.html`. Confirm the parameter CSVs, PRN, and shapefiles in that directory reflect the scenario you are documenting.
- Socio-economic pipeline: if Python dependencies are installed, trigger `python "inputs/SE Data/STOPS_SE_Data_Pipeline.py" --run_mode 2025AugRun` (use `conda run -n stops-py` if you isolated the environment). Review console warnings, row counts, and key fields in the produced DBFs before scaling up.
- Skim builder: open VSCode’s Jupyter support (`python -m notebook` or `jupyter notebook`) from the same terminal and launch `inputs/Skims/[RUN ME] run_builder.ipynb`. The notebook delegates to `skims_file_builder.py` with `skim_file_builder_configuration.json`; validate sample outputs before a full rebuild.
- Keep generated artefacts within their source directories so relative references and Excel links remain intact.
