"""
Purpose:
    Notebook-specific orchestrator for the STOPS data extraction pipeline.
    Executes PRN, EvO10, EvO9, and EvOSys extractions in the correct dependency order.
"""

import os
import sys
import logging
from pathlib import Path

# =============================================================================
# ENVIRONMENT SETUP & PATH FIX (JUPYTER NOTEBOOK SAFE)
# =============================================================================
# Dynamically find the project root
current_dir = Path(os.getcwd()).resolve()
if current_dir.name == "stops_data_parse":
    PROJECT_ROOT = current_dir.parent.parent
elif current_dir.name == "shop":
    PROJECT_ROOT = current_dir.parent
else:
    PROJECT_ROOT = current_dir

SHOP_DIR = PROJECT_ROOT / "shop"

# Reset working directory to project root for relative file paths to work
if os.getcwd() != str(PROJECT_ROOT):
    os.chdir(str(PROJECT_ROOT))

# Inject paths so Python can find the modules
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SHOP_DIR) not in sys.path:
    sys.path.insert(0, str(SHOP_DIR))

# --- THE IMPORT FIX ---
# Pipeline files are hardcoded to look for 'shop.base' instead of 'stops_data_parse.base'.
# Dynamically maps 'shop.base' to new location in memory.\
from stops_data_parse import base
sys.modules['shop.base'] = base
# ----------------------

# Now we can safely import the pipeline modules
from stops_data_parse import evo901, evo1001, evosys, prn1001

# Configure notebook logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    force=True # Forces reconfiguration in case Jupyter already set it
)

def run_notebook_pipeline():
    # Setup directories
    calibration_dir = PROJECT_ROOT / "calibration"
    tmp_dir = PROJECT_ROOT / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    logging.info("=== Starting STOPS Data Extraction Pipeline ===")

    try:
        # ---------------------------------------------------------------------
        # PRELIMINARY: Baseline Route Extraction
        # ---------------------------------------------------------------------
        logging.info("Running baseline Route-Level Extraction (nb_evo10.csv)...")
        evo1001.main([
            "--column-indices", "7", "8", "9",
            "--output", str(tmp_dir / "nb_evo10.csv")
        ])

        # ---------------------------------------------------------------------
        # 2050 NETWORK: System-Level Aggregation
        # ---------------------------------------------------------------------
        logging.info("Running System-Level Aggregation for 2050 Network...")
        evosys.main([
            "--calibration-workbook", str(calibration_dir / "Boston_Regional_STOPS Calibration Report_2050.xlsx"),
            "--evo9-csv", "evo9_01.csv",
            "--evo10-csv", "evo10_01.csv",
            "--output", "evosys_estimates.csv"
        ])

        # ---------------------------------------------------------------------
        # 2024 Stop-Level Data
        # ---------------------------------------------------------------------
        logging.info("Running Part 1: Stop-Level Extraction (tmp/evo901.csv)...")
        evo901.main([
            "--output", str(tmp_dir / "evo901.csv"),
            "--column-indices", "8", "9", "10", "11", "12"
        ])

        # ---------------------------------------------------------------------
        # 2024 & 2050 Route-Level Data
        # ---------------------------------------------------------------------
        logging.info("Running Part 2: Route-Level Extraction (tmp/evo101.csv)...")
        evo1001.main([
            "--output", str(tmp_dir / "evo101.csv"),
            "--column-indices", "8", "9", "10"
        ])

        # ---------------------------------------------------------------------
        # SYSTEM AGGREGATIONS
        # ---------------------------------------------------------------------
        logging.info("Running System Aggregation: Combined (tmp/evosys.csv)...")
        evosys.main([
            "--evo9-csv", str(tmp_dir / "evo901.csv"),
            "--evo10-csv", str(tmp_dir / "evo101.csv"),
            "--output", str(tmp_dir / "evosys.csv")
        ])

        logging.info("Running System Aggregation: Stop-Level Only (tmp/evosys_901.csv)...")
        evosys.main([
            "--evo9-csv", str(tmp_dir / "evo901.csv"),
            "--output", str(tmp_dir / "evosys901.csv")
        ])

        logging.info("Running System Aggregation: Route-Level Only (tmp/evosys_1001.csv)...")
        evosys.main([
            "--evo10-csv", str(tmp_dir / "evo101.csv"),
            "--output", str(tmp_dir / "evosys1001.csv")
        ])

        # ---------------------------------------------------------------------
        # FINAL ROUTE SUMMARY
        # ---------------------------------------------------------------------
        logging.info("Running PRN1001: Route-level summary by scenario year...")
        # Explicitly pass the output argument so it overrides kernel defaults to provide prn1001.py with expected argument
        prn1001.main([
            "--output", str(tmp_dir / "evo101.csv")
        ])

        logging.info("=== Pipeline Completed Successfully ===")

    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)

# Execute inside the cell
run_notebook_pipeline()