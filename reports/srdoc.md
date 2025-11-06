# Boston Regional STOPS Summary Report — Execution Flow

The `Boston_Regional_STOPS_Summary_Report.rmd` document is structured as a single knit that loads data, derives diagnostic tables, and then renders narrative sections in sequence. The flow below highlights the major execution stages and how each depends on earlier work.

```mermaid
flowchart TD
    subgraph S1["Section 1: Setup & Data Loading"]
        A["Start Knit<br/>YAML metadata invokes render()"] --> B["Setup chunk<br/>Clear workspace, load libraries"]
        B --> C["Read parameters & survey CSVs<br/>1-parameters, key routes, key stations"]
        C --> D["Define helper utilities<br/>Sorting, matrix builders, readers"]
        D --> E["Read STOPS control file<br/>Parse WALKCONTYPE & GTFS prefixes"]
        E --> F["Read STOPS results PRN<br/>Scan tables & diagnostics"]
        F --> G["Post-processing<br/>Top-N selections, list aggregation"]
        G --> H["Load spatial data<br/>District & station shapefiles"]
    end
    H --> I["Section 2: Settings & Inputs<br/>Metadata, GTFS listings, district/station definitions, maps, socio-economics"]
    I --> J["Section 3: Calibration Summaries<br/>Regional factors, linked trips, modal shares, station adjustments"]
    J --> K["Section 4: No Build vs Existing<br/>Compare assumptions, incremental trips, ridership responses"]
    K --> L["Section 5: Build vs No Build<br/>Project assumptions, project trips, CIG metrics"]
    L --> M["Section 6: Detailed Operations<br/>Station/route boards, transfers, flows, leaflet & reactable outputs"]
    M --> N["Finish Knit<br/>Writes BostonRegionalSTOPS_Summary.html"]
```

### Stage Notes
- **Section 1 – Setup & Data Loading:** Chunks `## 0.0`–`0.9` reset the workspace, load libraries, read CSV parameters, define helper functions, parse the STOPS control file, stream the `.prn` results, and prepare sorted lists plus shapefiles.
- **Section 2 – Settings & Inputs:** Presents STOPS configuration, GTFS inventories, district/station definitions, maps, and socio-economic context built from previously loaded objects.
- **Section 3 – Calibration Summaries:** Uses calibration tables and survey comparisons to show linked trips, modal shares, transfer rates, and station adjustments.
- **Section 4 – No Build vs Existing:** Compares base and no-build assumptions, incremental trips, and ridership responses using stored diagnostics.
- **Section 5 – Build vs No Build:** Highlights project assumptions, incremental trips, VMT impacts, and CIG metrics derived from earlier tables.
- **Section 6 – Detailed Operations:** Delivers detailed station/route boards, transfers, and flow visualizations (leaflet/reactable) built on the processed datasets.
- **Completion:** The knit hook in the YAML writes `BostonRegionalSTOPS_Summary.html` after all sections finish.

### File Inputs
- `reports/Summary_HTML_Report/1-parameters.csv` — Scenario metadata, file paths, and calibration flags consumed during setup.
- `reports/Summary_HTML_Report/2-keyroutes.csv` — Route IDs highlighted in corridor-level summaries.
- `reports/Summary_HTML_Report/3-keystations.csv` — Station group definitions and project station highlights.
- `reports/Summary_HTML_Report/Boston_2050.ctl` *(via `STOPSControlFile` parameter)* — STOPS control file parsed to extract GTFS prefixes, dates, and walk connector settings.
- `reports/Summary_HTML_Report/A2_MBTA-CATA-MWRTA-BATA-MVRTA#MBTA50-CATA-MWRTA-BATA-MVRTA#MBTA50-CATA-MWRTA-BATA-MVRTA_STOPSY2050Results.prn` *(via `STOPSResultsFile` parameter)* — Main STOPS results dump scanned for calibration tables, ridership summaries, and D2D matrices.
- `reports/Summary_HTML_Report/STOPSStations.shp` *(plus .dbf/.shx/.prj sisters via `STOPSStationSHPFile`)* — Station geometry and attributes used in maps and station-based summaries.
- `reports/Summary_HTML_Report/A2_DistrictZone.shp` *(plus .dbf/.shx/.prj via `STOPSDistrictSHPFile`)* — District polygon layer for mapping and D2D matrix labeling.
- `reports/Summary_HTML_Report/custom.css` — Theme overrides applied by the readthedown template.
- `reports/Summary_HTML_Report/Boston_MPO_Logo.png` — Branding asset injected into the document header.

### File Outputs
- `reports/Summary_HTML_Report/BostonRegionalSTOPS_Summary.html` — Final rendered HTML report written by the knit hook.

* Summary_HTML_Report TOC
```markdown
  - 1.0 r HTMLTitle
  - 2.0 Settings & Inputs
      - 2.1 Primary Settings {.tabset}
      - 2.2 GTFS Network
          - 2.2.1 Routes
          - 2.2.2 GTFS Connectors
      - 2.3 Tabulation & Calibration Setups
          - 2.3.1 Districts
          - 2.3.2 Station Groups
      - 2.4 District Map
      - 2.5 Population & Employment
          - 2.5.1 Corridor-Level
          - 2.5.2 Regional-Level
      - 2.6 Auto Speeds
      - 2.7 Demand Data
          - 2.7.1 Consistency of Ridership Information
          - 2.7.2 Transit Trip Targets
  - 3.0 Existing Conditions & Calibration Results
      - 3.1 Calibration Settings
          - 3.1.1 CTPP and Station Group Calibration Settings
          - 3.1.2 Fixed-Guideway Settings (FGS)
      - 3.2 Regional Adjustment Factor & Unlinked Trips
      - 3.3 Linked Trips
          - 3.3.1 By Trip Purpose
          - 3.3.2 By Auto Ownership
      - 3.4 District-to-District (D2D) Flows
      - 3.5 Linked Trips By Mode of Access
      - 3.6 Systemwide Transfer Rate
      - 3.7 Modal Shares (Overall)
      - 3.8 Station Group Calibration Factors
      - 3.9 Corridor Route-Level Boardings
      - 3.10 Mode of Access at Stations
  - 4.0 No-Build Assumptions & Results
      - 4.1 Changes in Assumptions
          - 4.1.1 Population & Employment
          - 4.1.2 Changes in Auto Speeds
          - 4.1.3 Transit Service Levels
          - 4.1.4 Park-Ride Lots
      - 4.2 Incremental Transit Trips (No Build - Existing)
      - 4.3 Ridership Responses (Loading/Assignment Data)
          - 4.3.1 Route-Level Boardings
          - 4.3.2 Mode of Access at Stations
  - 5.0 Build Assumptions & Results
      - 5.1 Changes in Assumptions
          - 5.1.1 Population & Employment
          - 5.1.2 Auto Speeds
          - 5.1.3 Transit Service Levels
          - 5.1.4 Park-Ride Lots
      - 5.2 Project Trips
      - 5.3 Ridership Responses (Loading/Assignment Data)
          - 5.3.1 Project Station-to-Station Flows
          - 5.3.2 Mode of Access at Stations
          - 5.3.3 Route-Level Boardings
      - 5.4 Incremental Transit Trips (Build - No Build)
      - 5.5 Incremental VMT (Build - No Build)
      - 5.6 Capital Investment Grant (CIG) Metrics
  - 6.0 Technical Appendix
      - 6.1 Station Boardings by Mode of Access (Daily)
      - 6.2 Route-Level Boardings by Production-End Mode-of-Access (Daily)
      - 6.3 Route-Level Boardings by Station Group (Daily)
      - 6.4 Route-Level Trips, Miles and Hours
          - 6.4.1 Peak Period
          - 6.4.2 Off-Peak Period
      - 6.5 Route-Level Boardings by Route Specific Mode-of-Access (Daily)
      - 6.6 Route-to-Route Transfers (Daily)
      - 6.7 Summary of Linked Transit Trips Trips
      - 6.8 Project Station-to-Station Flows
  - References
```


### Input/Output Sequence
```mermaid
sequenceDiagram
    participant Knit as rmarkdown::render
    participant Setup as Section1:Setup
    participant Control as Control Parser
    participant Results as PRN Scanner
    participant Spatial as Spatial Loader
    participant Report as Sections2-6

    Knit->>Setup: Load libraries\nread 1-parameters.csv
    Setup->>Setup: read 2-keyroutes.csv\nread 3-keystations.csv
    Setup->>Control: pass STOPSControlFile path
    Control->>Control: open Boston_2050.ctl\nparse GTFS metadata
    Control-->>Setup: GTFS table\nWalk connector flag
    Setup->>Results: pass STOPSResultsFile path
    Results->>Results: stream A2_...Results.prn\npopulate diagnostics, tables
    Results-->>Setup: calibration objects\nD2D matrices
    Setup->>Spatial: pass shapefile paths
    Spatial->>Spatial: load STOPSStations.shp\nload A2_DistrictZone.shp
    Spatial-->>Setup: spatial data frames
    Setup-->>Report: inputs assembled
    Report->>Knit: render sections 2-6 using loaded data
    Knit-->>Report: write BostonRegionalSTOPS_Summary.html
```
*Participants: `Knit` represents `rmarkdown::render`, `Setup` encapsulates the Section 1 preparation chunks, `Control` parses the STOPS control file, `Results` streams the `.prn` diagnostics, `Spatial` loads shapefiles, and `Report` covers Sections 2–6 that consume those objects.*


### Python Migration Feasibility & Risks
- **Component Footprint:** Each section leans heavily on R-specific constructs—`dplyr` pipelines, `knitr`/`kableExtra` formatting, `leaflet`/`reactable` widgets, and GDAL bindings via `rgdal`. Recreating these in Python would require equivalent stacks (e.g., pandas, geopandas, folium, plotly/dash tables) and reimplementation of ~3,500 lines of orchestration logic, including bespoke matrix parsers and summarizers.
- **Helper Functions:** The utility suite (matrix sorting, aggregation, fixed-width PRN readers, shapefile handling) would need end-to-end rewrites. Many rely on R idioms (e.g., `addmargins`, `read.fwf`, `kable_styling`) without direct Python analogues, raising effort and regression risk if behavior diverges.
- **Report Rendering:** The document’s R Markdown workflow bundles narrative, inline calculations, and HTML widgets in one knit. Porting to a Python framework (Jupyter, nbconvert, Sphinx, or static site generators) requires redesigning layout, templating, and widget embedding. Matching the existing readthedown theme and table styling would add extra front-end work.
- **Package Parity Risks:** Critical dependencies such as `rgdal` (soon superseded by `sf`/`terra`) and `RStudioConsoleRender` lack straightforward Python replacements. Loss of these could break shapefile ingestion or interactive console outputs unless custom pipelines or APIs are introduced.
- **Data Pipeline Stability:** Calibration lists, GTFS parsing, and D2D matrix logic are tightly coupled to R data frames. Any misalignment in type handling or floating-point formatting during a port could cascade into incorrect metrics in downstream sections (Sections 3–6).
- **Migration Recommendation:** A phased approach—first modularizing R helpers and adding automated tests—would reduce risk before attempting Python parity. Without such scaffolding, a direct migration risks extended downtime for the reporting workflow and inconsistent deliverables.
