###########################################################################
#
#   Author : Naveen Chandra Iraganaboina
#   Organization: Insight Transportation Consulting
#   
###########################################################################

rm(list = ls())   ## Clear memory

start_time <- Sys.time()
options(digits = 10, warn = -1)

library(dplyr)
library(stringr)
library(data.table)
library(future.apply)
library(progress)
library(readr)
library(openxlsx)

# Parallel plan (use multisession for Windows, multicore for Linux/Mac)
plan(multisession)

# Load Parameters and read them
Input_parameters <- "Inputs/Input_Data&Parameters.xlsx"
Mode_Lookup_df <- read.xlsx(xlsxFile = Input_parameters, sheet = "Route_Mode_Lookup")
GTFS_suffix <- read.xlsx(xlsxFile = Input_parameters, sheet = "GTFS")
report_fileName <- read.xlsx(xlsxFile = Input_parameters, sheet = "Results.prn")

# Output Folder
Output_location <- "Outputs/"

# check if the output folder exists and delete any files in it, else create one
if (dir.exists(Output_location)) {
  # Delete all files in the folder (but not subfolders)
  files <- list.files(Output_location, full.names = TRUE)
  invisible(file.remove(files))
} else {
  dir.create(Output_location, recursive = TRUE)
}

# Load STOPS report
report_file <- paste0("Inputs/", report_fileName$FileName[1])
Stops_data <- readLines(report_file, warn = FALSE)

#=====================================================================
#                 All the Functions used in the script
#=====================================================================

# Read routes.txt from the GTFS folders
read_routes <- function(folder) {
  file_path <- file.path(folder, "routes.txt")
  if (file.exists(file_path)) {
    routes <- read_csv(file_path, show_col_types = FALSE, col_types = cols(.default = "c"))
    routes$Source_GTFS <- basename(folder)  # Add a column for source folder
    return(routes)
  } else {
    warning(paste("routes.txt not found in", folder))
    return(NULL)
  }
}

# Clean the Data frames of extra spaces
clean_spaces <- function(df) {
  df[] <- lapply(df, function(col) {
    if (is.character(col)) trimws(col, which = "both") else col
  })
  return(df)
}

# Extract the sub-table index list (e.g., 1023.00002, etc.)
Extract_ListOfTables <- function(TableNo) {
  TableID <- paste0("Table  ", TableNo)
  Tableformat <- c(26, 26, 12)
  
  L <- which(grepl(TableID, Stops_data))
  if (length(L) == 0) return(NULL)
  
  TableStartLine <- L + 3
  TableEndLine <- min(Break_points[Break_points > TableStartLine])
  Table_text <- Stops_data[TableStartLine:TableEndLine]
  
  con <- textConnection(Table_text)
  Table_df <- read.fwf(con, widths = Tableformat, header = FALSE, stringsAsFactors = FALSE)
  close(con)
  
  colnames(Table_df) <- Table_df[1, ]
  Table_df <- Table_df[3:(nrow(Table_df) - 3), ]
  return(Table_df)
}

# Extract individual trip-level tables
Extract_TripLevelTable <- function(TableInfo) {
  #TableNo <- as.numeric(trimws(TableInfo$`Table No.`))
  TableNo <- trimws(TableInfo$`Table No.`)
  Tableformat <- c(10, 8, 26, 41, 10, 11, 12, 10)
  
  L <- Table_lines[as.character(TableNo)]
  if (is.na(L)) return(NULL)
  
  TableStartLine <- L + 6
  TableEndLine <- min(Break_points[Break_points > TableStartLine])
  Table_text <- Stops_data[TableStartLine:TableEndLine]
  
  con <- textConnection(Table_text)
  Table_df <- read.fwf(con, widths = Tableformat, header = FALSE, stringsAsFactors = FALSE)
  close(con)
  
  colnames(Table_df) <- Table_df[1, ]
  Table_df <- Table_df[4:(nrow(Table_df) - 3), ]
  
  TG_No_line <- Stops_data[L + 2]
  TG_No <- as.numeric(str_sub(TG_No_line, -4))
  
  Table_df$Route_ID <- TableInfo$ROUTE
  Table_df$Trip_ID <- TableInfo$TRIP_ID
  Table_df$Trip_ID_number <- TG_No
  
  colnames(Table_df) <- gsub(" ", "", colnames(Table_df))
  Table_df <- Table_df %>% select(Route_ID, Trip_ID, Trip_ID_number, Stop_seq, Stop_ID, Stop_Name, Boards, Alights)
  
  return(Table_df)
}


# A helper function to extract and write a full scenario group
Extract_Group <- function(table_code) {
  message("Processing table ", table_code)
  Table_List <- Extract_ListOfTables(table_code)
  if (is.null(Table_List)) {
    warning("No entries found for table ", table_code)
    return()
  }
  
  pb <- progress_bar$new(
    format = " [:bar] :percent eta: :eta",
    total = nrow(Table_List), clear = FALSE, width = 60
  )
  
  Results <- lapply(1:nrow(Table_List), function(i) { #future_lapply
    pb$tick()
    Extract_TripLevelTable(Table_List[i, ])
  })
  
  Final <- bind_rows(Results)
  Final <- clean_spaces(Final)
  Final$Boards <- as.numeric(Final$Boards)
  Final$Alights <- as.numeric(Final$Alights)
  #fwrite(Final, output_file)
  return(Final)
}


# Extract Table 10.01 (Route Level Summary)
Extract_Table10.01 <- function(Table = "Table    10.01"){
  
  Tableformat <- c(25, 31, 9, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 9)
  L <- which(grepl(Table, Stops_data)) 
  if (is.na(L)) return(NULL)
  
  TableStartLine <- L + 7
  TableEndLine <- min(Break_points[Break_points > TableStartLine])
  Table_text <- Stops_data[TableStartLine:TableEndLine]
  
  con <- textConnection(Table_text)
  Table_df <- read.fwf(con, widths = Tableformat, header = FALSE, stringsAsFactors = FALSE)
  close(con)
  
  colnames(Table_df) <- c("Route_ID", "Route_Name", "Observed_Count", 
                          "Exist_WLK", "Exist_KNR", "Exist_PNR", "Exist_ALL",
                          "NB_WLK", "NB_KNR", "NB_PNR", "NB_ALL",
                          "Build_WLK", "Build_KNR", "Build_PNR", "Build_ALL")
  Table_df <- Table_df[3:(nrow(Table_df) - 3), ]
  
  Table_df <- clean_spaces(Table_df)
  
  Table_df[, 3:15] <- lapply(Table_df[, 3:15], function(x) as.numeric(trimws(x)))
  
  GTFS_suffix_tmp <- GTFS_suffix %>% select(-GTFS) %>% unique()
  Table_df2 <- Table_df %>%
    mutate(Suffix = ifelse(grepl("&[A-Z]", Route_ID),
                           regmatches(Route_ID, regexpr("&[A-Z]", Route_ID)), NA)) %>%
    left_join(GTFS_suffix_tmp, by = "Suffix") %>%
    select(Agency, everything(), -Suffix)
  
  return(Table_df2)
}

# Extract Table 9.01 (Stop Level Summary)
Extract_Table9.01 <- function(Table = "Table     9.01"){
  Tableformat <- c(26, 21, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,10,10)
  L <- which(grepl(Table, Stops_data)) 
  if (is.na(L)) return(NULL)
  
  T_break2 <- paste0("\f",strrep("=",129))
  Break_points2 <- which(grepl(T_break2,Stops_data))  
  
  TableStartLine <- L + 7
  #TableEndLine <- min(Break_points[Break_points > TableStartLine])
  TableEndLine2 <- min(Break_points2[Break_points2 > TableStartLine])
  Table_text <- Stops_data[TableStartLine:TableEndLine2]
  
  con <- textConnection(Table_text)
  Table_df <- read.fwf(con, widths = Tableformat, header = FALSE, stringsAsFactors = FALSE)
  close(con)
  
  colnames(Table_df) <- c("Stop_ID", "Station_Name",  
                          "Exist_WLK", "Exist_KNR", "Exist_PNR", "Exist_XFR", "Exist_ALL",
                          "NB_WLK", "NB_KNR", "NB_PNR", "NB_XFR","NB_ALL",
                          "Build_WLK", "Build_KNR", "Build_PNR", "Build_XFR", "Build_ALL")
  Table_df <- Table_df[3:(nrow(Table_df) - 3), ]
  
  Table_df <- clean_spaces(Table_df)
  
  Table_df[, 3:17] <- lapply(Table_df[, 3:17], function(x) as.numeric(trimws(x)))

  GTFS_suffix_tmp <- GTFS_suffix %>% select(-GTFS) %>% unique()
  Table_df2 <- Table_df %>%
    mutate(Suffix = ifelse(grepl("&[A-Z]", Stop_ID),
                           regmatches(Stop_ID, regexpr("&[A-Z]", Stop_ID)), NA)) %>%
    left_join(GTFS_suffix_tmp, by = "Suffix") %>%
    select(Agency, everything(), -Suffix)
  
  return(Table_df2)
}

#==============================================================================
#                 Basic steps for the script
#==============================================================================

# Read Route information from GTFS and combine the information 
gtfs_dir <- "Inputs"
gtfs_folders <- list.dirs(gtfs_dir, recursive = FALSE, full.names = TRUE)

all_routes <- bind_rows(lapply(gtfs_folders, read_routes))
all_routes <- all_routes %>% select("route_id", "route_short_name", "route_long_name", 
                                    "route_type", "Source_GTFS" ) %>%
  left_join(GTFS_suffix, by = c("Source_GTFS" = "GTFS")) %>%
  mutate(route_id = paste0(route_id, Suffix)) %>%
  select(-Suffix) %>% distinct(route_id, .keep_all = TRUE)

# Identify break lines
Break_points <- which(grepl(strrep("-", 133), Stops_data))

# Pre-cache all table header lines and their start indexes
Table_lines <- grep("^Table\\s+102[3-8]\\.\\d{5}", Stops_data)
Table_index <- str_extract(Stops_data[Table_lines], "102[3-8]\\.\\d+")
names(Table_lines) <- Table_index


#==============================================================================
#   Route & Stop Level Estimates for the three scenarios
#==============================================================================

# Table groups (main indices like 1023.01)
TABLES <- c(  PEAK_EXIST = "1023.01",
              OFFPEAK_EXIST = "1024.01",
              PEAK_NOBUILD = "1025.01",
              OFFPEAK_NOBUILD = "1026.01",
              PEAK_BUILD = "1027.01",
              OFFPEAK_BUILD = "1028.01" )

# Run all scenarios and add time of day (TOD) column
PK_Exist <- Extract_Group(TABLES["PEAK_EXIST"])
PK_Exist$TOD <- "Peak"
OP_Exist <- Extract_Group(TABLES["OFFPEAK_EXIST"])
OP_Exist$TOD <- "Off Peak"
PK_NB <- Extract_Group(TABLES["PEAK_NOBUILD"])
PK_NB$TOD <- "Peak"
OP_NB <- Extract_Group(TABLES["OFFPEAK_NOBUILD"])
OP_NB$TOD <- "Off Peak"
PK_Build <- Extract_Group(TABLES["PEAK_BUILD"])
PK_Build$TOD <- "Peak"
OP_Build <- Extract_Group(TABLES["OFFPEAK_BUILD"])
OP_Build$TOD <- "Off Peak"

# Merge peak and off peak data to create data for each scenario
Exist <- bind_rows(PK_Exist, OP_Exist) %>%
                  left_join(all_routes, by = c("Route_ID" = "route_id"))%>%
                  group_by(Agency, Route_ID, route_short_name, route_long_name, Stop_ID, Stop_Name, route_type) %>%
                  summarise( Boards = sum(as.numeric(Boards), na.rm = TRUE),
                              Alights = sum(as.numeric(Alights), na.rm = TRUE)) %>%
                  mutate(FGS = case_when(route_type == "0" ~ "Partial",
                                         route_type == "3" ~ "None",
                                         TRUE ~ "FULL")) %>%
                  left_join(Mode_Lookup_df, by = "Route_ID")

NB <- bind_rows(PK_NB, OP_NB) %>%
                  left_join(all_routes, by = c("Route_ID" = "route_id"))%>%
                  group_by(Agency, Route_ID, route_short_name, route_long_name, Stop_ID, Stop_Name, route_type) %>%
                  summarise( Boards = sum(as.numeric(Boards), na.rm = TRUE),
                             Alights = sum(as.numeric(Alights), na.rm = TRUE),
                             .groups = "drop" ) %>%
                  mutate(FGS = case_when(route_type == "0" ~ "Partial",
                                         route_type == "3" ~ "None",
                                         TRUE ~ "FULL")) %>%
                  left_join(Mode_Lookup_df, by = "Route_ID")

Build <- bind_rows(PK_Build, OP_Build) %>%
                  left_join(all_routes, by = c("Route_ID" = "route_id"))%>%
                  group_by(Agency, Route_ID, route_short_name, route_long_name, Stop_ID, Stop_Name, route_type) %>%
                  summarise( Boards = sum(as.numeric(Boards), na.rm = TRUE),
                             Alights = sum(as.numeric(Alights), na.rm = TRUE),
                             .groups = "drop" ) %>%
                  mutate(FGS = case_when(route_type == "0" ~ "Partial",
                                         route_type == "3" ~ "None",
                                         TRUE ~ "FULL")) %>%
                  left_join(Mode_Lookup_df, by = "Route_ID")


# Write Route and Stop Level Estimates to Output folder
fwrite(Exist, paste0(Output_location,"Route&StopLevel_Estimates_Existing.csv"))
fwrite(NB, paste0(Output_location,"Route&StopLevel_Estimates_No-Build.csv"))
fwrite(Build, paste0(Output_location,"Route&StopLevel_Estimates_Build.csv"))


#==============================================================================
#   Route Level Estimates from Table 10.01 (For cross check purpose)
#==============================================================================

# T10.01 <- Extract_Table10.01()
# fwrite(T10.01, paste0(Output_location,"RouteLevelSummary_Table10.01_Debug.csv"))


#=================================================================================
#  Stop Level & Access Mode Estimates for the three scenarios from Table 9.01
#=================================================================================

# Extract Table 9.01 and write it out for cross checking
 T9.01 <- Extract_Table9.01()
# fwrite(T9.01, paste0(Output_location, "StopLevelAccessMode_Summary_Table9.01_Debug.csv"))

# Split the Table 9.01 to scenarios
T9.01_Exist <- T9.01 %>% select("Agency", "Stop_ID", "Station_Name", 
                                "Exist_WLK", "Exist_KNR", "Exist_PNR", "Exist_XFR", "Exist_ALL") %>%
                  rename_with(~ sub("^Exist_", "", .x), starts_with("Exist_"))
T9.01_NB <- T9.01 %>% select("Agency", "Stop_ID", "Station_Name", 
                                "NB_WLK", "NB_KNR", "NB_PNR", "NB_XFR", "NB_ALL") %>%
                  rename_with(~ sub("^NB_", "", .x), starts_with("NB_"))
T9.01_Build <- T9.01 %>% select("Agency", "Stop_ID", "Station_Name", 
                                "Build_WLK", "Build_KNR", "Build_PNR", "Build_XFR", "Build_ALL") %>%
                  rename_with(~ sub("^Build_", "", .x), starts_with("Build_"))

# Write the stop level and access mode estimates to output data
fwrite(T9.01_Exist, paste0(Output_location,"StopLevelAccessMode_Estimates_Existing.csv"))
fwrite(T9.01_NB, paste0(Output_location,"StopLevelAccessMode_Estimates_No-Build.csv"))
fwrite(T9.01_Build, paste0(Output_location,"StopLevelAccessMode_Estimates_Build.csv"))


#==============================================================================================
#   Route Level estimate summary from Route & Stop Level Estimates for the three scenarios 
#             for cross checking purposes
#==============================================================================================

# Estimate route level summary from route & stop level estimates
#       Use this to compare against Table 10.01
Exist_Rt_Summary <- Exist %>% group_by(Route_ID) %>%
                     summarise(Exist_Boards = sum(Boards, na.rm = TRUE))

NB_Rt_Summary <- NB %>% group_by(Route_ID) %>%
                  summarise(NB_Boards = sum(Boards, na.rm = TRUE))

Build_Rt_Summary <- Build %>% group_by(Route_ID) %>%
                  summarise(Build_Boards = sum(Boards, na.rm = TRUE))

Route_Summary <- Exist_Rt_Summary %>% full_join(NB_Rt_Summary, by = "Route_ID")  %>% 
                   full_join(Build_Rt_Summary, by = "Route_ID")

# Write the data to the output folder
# write.csv(Route_Summary, paste0(Output_location,"RouteLevelSummary_Debug.csv"))

print(".....................Program execution completed..............")

end_time <- Sys.time()
print(paste("Time elapsed", round((end_time - start_time),2) , "mins"))
