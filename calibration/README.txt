
##################################################################################################################################################

README – STOPS Results Table Extraction and Excel Calibration Report Preparation
June 2025

	Workflow Summary
========================
1. Extract tables from Results.prn as specified in R1_Table_Numbers_Input.txt
2. Split tables into columns using the layout defined in R2_Format_by_table.xlsx
3. Export extracted tables to A1_Extracted_Tables.xlsx
4. Apply formatting rules and write to A2_Formatted_Tables.xlsx
5. Link formatted tables to the Calibration Report Excel Template to generate a ready-to-review summary

##################################################################################################################################################


	Inputs
========================
R1_Table_Numbers_Input.txt			: List of STOPS tables to extract (Do not modify)
R2_Format_by_table.xlsx				: Column formatting rules for each table (Do not modify)
*Results.prn						: STOPS model output file from the current-year run


	R-Scripts
========================
Main_Program.rmd					: Main driver script to generate output files
Extract_STOPS_Tables.R				: Contains all reusable functions used by the main script


	Outputs
========================
A1_Extracted_Tables.xlsx			: Raw table data extracted from STOPS output
A2_Formatted_Tables.xlsx			: Cleaned and formatted table output for reporting


	Boston_Regional_STOPS Calibration Report_Template.xlsx
=============================================================
Excel template for summarizing STOPS calibration results. Includes observed vs. estimated summaries and charts.
The template was developed specifically for Boston Regional STOPS model current-year (2024) Type 00 and Type 12 calibration runs.
It does not automatically detect new GTFS routes or stops or districts or station groups. 
Manual edits may be needed for any such changes.


	How to Run the Script and Link Output to the Excel Template
==================================================================
1.  Prepare Files:
	Place the Results.prn file in the same directory as the input and script files.

2.  Run the Script in RStudio:
	Open and run Main_Program.rmd. 
	Line 29 of the script contains the filename for Results.prn
	
3.	Verify Output:
	Upon successful execution, the script will generate A2_Formatted_Tables.xlsx in the same directory.

4. 	Link to Excel Template:
	Make a copy of Boston_Regional_STOPS Calibration Report_Template.xlsx and rename it.
	Open both the renamed template and A2_Formatted_Tables.xlsx in Excel.

5.	Review Linked Data:
	The renamed template will reflect updated model results via formulae linked to A2_Formatted_Tables.xlsx

6.  Unlink Excel Files (Recommended for Portability):
	In the renamed calibration file:
		- Go to Data → Workbook Links (under Queries & Connections)
		- In the ribbon, click Break All to unlink the files
		- Save the renamed calibration file
	This ensures future iterations remain self-contained and shareable.
	
7.	Review Results:
	Your renamed calibration file is now ready for review and distribution.