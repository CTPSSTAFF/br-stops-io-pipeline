###########################################################################
#                                                                         #
#                                                                         #
#   Author : Naveen Chandra Iraganaboina
#   Title  : Extract and Format Tables from STOPS report
#                                                                         #   
#                                                                         #
#   R Version : 4.4.1
#   R Studio  : 2025.05.0 Build 496                       
#
#
#   This script can extract following tables from STOPs
#  ==========================================================
#   2.04   2.05
#   9.01
#   10.01  10.03  10.04  10.05  10.06
#   11.01  11.02  11.03  11.04
#   12.01
#   13.01  13.07  13.08
#   345.01  344.01
#
#
#   This script has functions that can format the following tables
#  ===============================================================
#  9.01
#  10.01  10.03  10.05  10.06
#
#
###########################################################################


library(openxlsx)      
library(iotools)


##############################################################
#
#       --------------------------------
#         Functions to Extract Tables
#       --------------------------------
#
##############################################################

# Function to create Table ids
format_table_ids <- function(ids){
  ids <- paste0("Table", strrep(" ",(9-nchar(ids))), ids)
  return(ids)
}


# Read .prn file
read_prn <- function(STOPS_Results_file){
  
  STOPS_data <- read.delim(STOPS_Results_file, skipNul = TRUE)
  return(STOPS_data)
}


# Function to strip the lines from the STOPS report for a specific table id
Extrat_Table <- function(data, id){
  T_break1 <- strrep("-",133)
  T_break2 <- paste0("\f",strrep("=",129))
  
  L <- which(grepl(id,data$STOPS_REPORT))
  L0 <- L-4
  L99_1 <- which(grepl(T_break1,data$STOPS_REPORT))  
  L99_1 <- L99_1[L99_1 > L0][1]
  L99_2 <- which(grepl(T_break2,data$STOPS_REPORT))  
  L99_2 <- L99_2[L99_2 > L0][1]
  L99 <- min(L99_2, L99_1)
  df <- data$STOPS_REPORT[L0:(L99-1)]
  
  return(df)
}


# Function to Split the lines appropriately and copy them to excel sheet (for tables)
To_excel <- function(df, workbook, id, table_format){
  
  
  id <- gsub(" ", "", id)
  df_description <- df[1:9]
  
  df_table <- df[10:(length(df))]

  df_table <- as.data.frame(df_table)
  max_char_len <- max(nchar(df_table$df_table))
  df_table$df_table[nchar(df_table$df_table) < max_char_len] <- paste0(df_table$df_table[nchar(df_table$df_table) < max_char_len],
                                                                       strrep(" ", (max_char_len-nchar(df_table$df_table[nchar(df_table$df_table) < max_char_len]))))
  a <- str_length(df_table$df_table)
  
  df_table <- dstrfw(df_table$df_table, widths = table_format,  
                     col_types = rep(c("character"),length(table_format)), 
                     strict = FALSE)
  writeData(workbook, sheet = id, xy=c(1,1), x=df_description)
  writeData(workbook, sheet = id, xy=c(1,10), x=df_table)
  
}

# Function to Split the lines appropriately and copy them to excel sheet (for D-D matrices)
Mat_to_excel <- function(df, workbook, id){
  id <- gsub(" ", "", id)
  
  if((grepl("======" , df[10]))){
    df_description <- df[1:8]
    df_mat_content <- df[9:length(df)]
  } else{
    df_description <- df[1:9]
    df_mat_content <- df[10:length(df)]
    # print(df_description)
    # print(df_mat_content)
    
  }
  
  len_mat <- length(df_mat_content)-1
  mat_format <- c(7, rep(9, len_mat-2), 8)
  
  df_mat <- dstrfw(df_mat_content, width=mat_format,  col_types = rep(c("character"),len_mat))
  #print(df_mat)
  #stop()
  writeData(workbook, sheet = id, xy=c(1,1), x=df_description)
  writeData(workbook, sheet = id, xy=c(1,10), x=df_mat)
}

# Function to Split the lines appropriately and copy them to excel sheet (for S-S matrices)
Mat_to_excel2 <- function(df, workbook, id){
  id <- gsub(" ", "", id)
  
  if((grepl("======" , df[16]))){
    df_description <- df[1:13]
    df_mat_content <- df[14:length(df)]
  } else if(id %in% "Table2.05"){
    df_description <- df[1:9]
    df_mat_content <- df[10:length(df)]
    # print(df_description)
    # print(df_mat_content)
    #stop()
  }  else{
    df_description <- df[1:14]
    df_mat_content <- df[15:length(df)]
  }
  
  
  df_mat_content <- df_mat_content[-2]
  
  if(id %in% "Table2.05"){
    len_mat <- length(df_mat_content)
  } else {
    len_mat <- length(df_mat_content) - 1
  }
  mat_format <- c(12, rep(7, len_mat-2), 7)
  max_char_len <- max(nchar(df_mat_content))
  
  df_mat_content[nchar(df_mat_content) < max_char_len] <- paste0(df_mat_content[nchar(df_mat_content) < max_char_len],
                                                                 strrep(" ", (max_char_len-nchar(df_mat_content[nchar(df_mat_content) < max_char_len]))))
  
  df_mat <- dstrfw(df_mat_content, width=mat_format,  col_types = rep(c("character"),len_mat))
  print(id)
  
  writeData(workbook, sheet = id, xy=c(1,1), x=df_description)
  writeData(workbook, sheet = id, xy=c(1,10), x=df_mat)
}


Extract_Table <- function(STOPS_Results_file, Tables_file, Format_input, Output_Excel){
  print("here")
  Tables <- read.delim(Tables_file)$Table_numbers
  print(Tables)
  Table_ids <- format_table_ids(Tables)
  print(Table_ids)
  TF <- read.xlsx(Format_input)
  #print("end- here")
  STOPS_data <- read.delim(STOPS_Results_file, skipNul = TRUE, quote = "")
  #print("end- here")
  STOPS_data <- rbind(colnames(STOPS_data), STOPS_data)
  colnames(STOPS_data) <- "STOPS_REPORT"
  #print("end- here")
  
  wb <- loadWorkbook(Output_Excel)
  sheet_names <- gsub(" ", "", Table_ids)
  
  
  for(sn in sheet_names){
    if(sn %in% sheets(wb)){ removeWorksheet(wb, sn) }
    addWorksheet(wb, sn, zoom = 80)
  }
  

  for(i in 1:length(Table_ids)){

    not_table <- c("District", "Station Group")
    print (Table_ids[i])
    id_tf <- TF$format[TF$Table.id == Tables[i]]
    cat("Yes1")
    id_tf2 <- as.integer(strsplit(id_tf,",")[[1]])  # If there is a error here; check the Format file
    #cat("Yes2")

    if(!(id_tf %in% not_table)) {
      df_contents <- Extrat_Table(STOPS_data, Table_ids[i])
      To_excel(df_contents, wb, Table_ids[i], id_tf2)
    } else if (id_tf == "District" ){
      print(paste(Table_ids[i], "not a table"))
      df_contents <- Extrat_Table(STOPS_data, Table_ids[i])
      
      Mat_to_excel(df_contents, wb, Table_ids[i])
    } else if (id_tf == "Station Group" ){
      print(paste(Table_ids[i], "not a table"))
      df_contents <- Extrat_Table(STOPS_data, Table_ids[i])
      
      Mat_to_excel2(df_contents, wb, Table_ids[i])
    }

  }

  saveWorkbook(wb, Output_Excel, overwrite = TRUE)

  
  return(1)
}



##############################################################
#
#       --------------------------------
#         Format the Extracted Tables
#       --------------------------------
#
##############################################################


Get_10.01 <- function(workbook, start_row = 13){
  T_10.01 <- read.xlsx(workbook, sheet = "Table10.01",startRow = start_row)
  colnames(T_10.01) <- c("Route_ID", "Route.Name", "Count_E", "WLK_E", "KNR_E", "PNR_E", "ALL_E", 
                                            "WLK_NB", "KNR_NB", "PNR_NB","ALL_NB", 
                                            "WLK_B", "KNR_B", "PNR_B", "ALL_B")
  
  T_10.01 <- T_10.01[2:(nrow(T_10.01)-2),]
  T_10.01 <- T_10.01 %>% mutate_all(function(y) str_squish(y))
  
  tmp <- c("Count_E", "WLK_E", "KNR_E", "PNR_E", "ALL_E", 
           "WLK_NB", "KNR_NB", "PNR_NB", "ALL_NB", 
           "WLK_B", "KNR_B", "PNR_B", "ALL_B")
  T_10.01 <- T_10.01 %>% mutate_at(tmp, function(y) as.numeric(y))
  
  return(T_10.01)
}


Get_10.03 <- function(workbook, start_row=14){
  T_10.03 <- read.xlsx(workbook, sheet = "Table10.03",startRow = start_row)
  tmp <- c("Route_ID", "Route_Name", "Trips_E", "Miles_E", "Hours_E",
           "Trips_NB", "Miles_NB", "Hours_NB",
           "Trips_B", "Miles_B", "Hours_B")
  colnames(T_10.03) <- tmp
  T_10.03 <- T_10.03[2:(nrow(T_10.03)-1),]
  T_10.03 <- T_10.03 %>% mutate_all(function(y) str_squish(y))
  
  T_10.03 <- T_10.03 %>% mutate_at(.vars = colnames(T_10.03)[3:ncol(T_10.03)],
                                   function(y) as.numeric(y))
  T_10.03$Speed_E <- T_10.03$Miles_E / T_10.03$Hours_E
  T_10.03$Speed_NB <- T_10.03$Miles_NB / T_10.03$Hours_NB
  T_10.03$Speed_B <- T_10.03$Miles_B / T_10.03$Hours_B
  return(T_10.03)
}

Get_10.04 <- function(workbook, start_row=14){
  T_10.04 <- read.xlsx(workbook, sheet = "Table10.04",startRow = start_row)
  tmp <- c("Route_ID", "Route_Name", "Trips_E", "Miles_E", "Hours_E",
           "Trips_NB", "Miles_NB", "Hours_NB",
           "Trips_B", "Miles_B", "Hours_B")
  colnames(T_10.04) <- tmp
  T_10.04 <- T_10.04[2:(nrow(T_10.04)-1),]
  T_10.04 <- T_10.04 %>% mutate_all(function(y) str_squish(y))
  
  T_10.04 <- T_10.04 %>% mutate_at(.vars = colnames(T_10.04)[3:ncol(T_10.04)],
                                   function(y) as.numeric(y))
  T_10.04$Speed_E <- T_10.04$Miles_E / T_10.04$Hours_E
  T_10.04$Speed_NB <- T_10.04$Miles_NB / T_10.04$Hours_NB
  T_10.04$Speed_B <- T_10.04$Miles_B / T_10.04$Hours_B
  return(T_10.04)
}


Get_10.05 <- function(workbook, start_row = 13){
  T_10.05 <- read.xlsx(workbook, sheet = "Table10.05",startRow = start_row)
  tmp <- c("Route_ID", "Route_Name", "Count_E", "WLK_E", "KNR_E", "PNR_E", "XFR_E", "ALL_E", 
           "WLK_NB", "KNR_NB", "PNR_NB", "XFR_NB", "ALL_NB", 
           "WLK_B", "KNR_B", "PNR_B", "XFR_B", "ALL_B",
           "WLK_PT", "KNR_PT", "PNR_PT", "XFR_PT", "ALL_PT")
  colnames(T_10.05) <- tmp
  T_10.05 <- T_10.05[2:(nrow(T_10.05)-2),]
  T_10.05 <- T_10.05 %>% mutate_all(function(y) str_squish(y))
  
  T_10.05 <- T_10.05 %>% mutate_at(.vars = colnames(T_10.05)[3:ncol(T_10.05)],
                                   function(y) as.numeric(y))
  return(T_10.05)
}


Get_10.06 <- function(workbook, start_row = 13){
  
  T_10.06 <- read.xlsx(workbook, sheet = "Table10.06",startRow = start_row)
  T_10.06 <- T_10.06[!(colnames(T_10.06) %in% "|")]
  T_10.06 <- T_10.06[2:(nrow(T_10.06)-3), ]
  T_10.06 <- T_10.06 %>% mutate_all(function(y) str_squish(y))
  T_10.06$`to--Route_ID` <- Reduce(function(x,y) if(y=="") x else y, T_10.06$`to--Route_ID`, accumulate = T)
  T_10.06$`--Route.Name` <- Reduce(function(x,y) if(y=="") x else y, T_10.06$`--Route.Name`, accumulate = T)
  T_10.06$`from--Route_ID`[T_10.06$`from--Route_ID` %in% ""] <- T_10.06$`--Route.Name.1`[T_10.06$`from--Route_ID` %in% ""]
  T_10.06[c("from--Route_ID.1", "--Route.Name.2", "from--Route_ID.2", "--Route.Name.3")] <- NULL
  colnames(T_10.06)[colnames(T_10.06) %in% "Transfers"] <- "Transfers_E"
  colnames(T_10.06)[colnames(T_10.06) %in% "Transfers.1"] <- "Transfers_NB"
  colnames(T_10.06)[colnames(T_10.06) %in% "Transfers.2"] <- "Transfers_B"
  colnames(T_10.06)[colnames(T_10.06) %in% "--Route.Name"] <- "To_Route_Name"
  colnames(T_10.06)[colnames(T_10.06) %in% "--Route.Name.1"] <- "From_Route_Name"
  
  T_10.06 <- T_10.06 %>% mutate_at(.vars = colnames(T_10.06)[5:ncol(T_10.06)],
                                   function(y) as.numeric(y))
  
  T_10.06_totals <- T_10.06 %>% filter(`from--Route_ID` %in% "Total transfers") 
  T_10.06_totals <- aggregate(T_10.06_totals[c("Transfers_E", "Transfers_NB", "Transfers_B")], 
                              by = T_10.06_totals[c("to--Route_ID", "To_Route_Name", "from--Route_ID",
                                                    "From_Route_Name")], function(x) sum(x))
  colnames(T_10.06_totals) <- c("to--Route_ID", "To_Route_Name", "from--Route_ID", "From_Route_Name", 
                                "Transfers_Total_E", "Transfers_Total_NB", "Transfers_Total_B")
  
  
  T_10.06_summary <- T_10.06 %>% filter(!(T_10.06$`from--Route_ID` %in% "Total transfers") )
  T_10.06_summary <- aggregate(T_10.06_summary[c("Transfers_E", "Transfers_NB", "Transfers_B")], 
                               by = T_10.06_summary[c("to--Route_ID", "To_Route_Name")], function(x) sum(x))
  colnames(T_10.06_summary) <- c("to--Route_ID", "To_Route_Name",  
                                 "Transfers_Sum_E", "Transfers_Sum_NB", "Transfers_Sum_B")
  
  T_10.06_summary <- left_join(T_10.06_summary, T_10.06_totals, by=c("to--Route_ID", "To_Route_Name"))
  T_10.06_summary[c("from--Route_ID", "From_Route_Name")] <- NULL
  
  return(list(T_10.06, T_10.06_summary))
}



Get_9.01 <- function(workbook, start_row = 13){
  T_9.01 <- read.xlsx(workbook, sheet = "Table9.01",startRow = start_row)
  tmp <- c("STOP_ID1", "STOP_Name", "WLK_E", "KNR_E", "PNR_E", "XFR_E", "ALL_E", 
           "WLK_NB", "KNR_NB", "PNR_NB", "XFR_NB", "ALL_NB", 
           "WLK_B", "KNR_B", "PNR_B", "XFR_B", "ALL_B")
  colnames(T_9.01) <- tmp
  T_9.01 <- T_9.01[2:(nrow(T_9.01)-1),]
  T_9.01 <- T_9.01 %>% mutate_all(function(y) str_squish(y))
  
  T_9.01 <- T_9.01 %>% mutate_at(.vars = colnames(T_9.01)[3:ncol(T_9.01)],
                                   function(y) as.numeric(y))
  
  return(T_9.01)
}

Get_11.01 <- function(workbook, start_row = 10){
  T_11.01 <- read.xlsx(workbook, sheet = "Table11.01", startRow = start_row)
  T_11.01 <- T_11.01[c("V1", "V2", "V3", "V5", "V6", "V8", "V9", "V11", "V12", "V14", "V15")]
  tmp <- c("HH Cars", "Sub-mode", "Access mode", "Model_E", "Survey_E",
           "Model_NB", "Survey_NB", "Model_B", "Survey_B", "Project_B", "survey2_B")
  colnames(T_11.01) <- tmp
  T_11.01 <- T_11.01[4:nrow(T_11.01),]
  T_11.01 <- T_11.01 %>% mutate_all(function(y) str_squish(y))
  T_11.01 <-subset(T_11.01, !(T_11.01$`HH Cars` %in% ""  ))
  T_11.01 <-subset(T_11.01, !(T_11.01$`Sub-mode` %in% c("------------------ -", 
                                                        "================== =", 
                                                        ". . . . . . . . . .")))
  T_11.01 <-subset(T_11.01, !(T_11.01$Survey_E %in% c("-------", 
                                                      "=======", 
                                                      ". . . .")))
  
  T_11.01 <- T_11.01 %>% mutate_at(.vars = colnames(T_11.01)[4:ncol(T_11.01)],
                                   function(y) as.numeric(y))
  return(T_11.01)
}


Get_11.02 <- function(workbook, start_row = 10){
  T_11.01 <- read.xlsx(workbook, sheet = "Table11.02", startRow = start_row)
  T_11.01 <- T_11.01[c("V1", "V2", "V3", "V5", "V6", "V8", "V9", "V11", "V12", "V14", "V15")]
  tmp <- c("HH Cars", "Sub-mode", "Access mode", "Model_E", "Survey_E",
           "Model_NB", "Survey_NB", "Model_B", "Survey_B", "Project_B", "survey2_B")
  colnames(T_11.01) <- tmp
  T_11.01 <- T_11.01[4:nrow(T_11.01),]
  T_11.01 <- T_11.01 %>% mutate_all(function(y) str_squish(y))
  T_11.01 <-subset(T_11.01, !(T_11.01$`HH Cars` %in% ""  ))
  T_11.01 <-subset(T_11.01, !(T_11.01$`Sub-mode` %in% c("------------------ -", 
                                                        "================== =", 
                                                        ". . . . . . . . . .")))
  T_11.01 <-subset(T_11.01, !(T_11.01$Survey_E %in% c("-------", 
                                                      "=======", 
                                                      ". . . .")))
  
  T_11.01 <- T_11.01 %>% mutate_at(.vars = colnames(T_11.01)[4:ncol(T_11.01)],
                                   function(y) as.numeric(y))
  return(T_11.01)
}


Get_11.03 <- function(workbook, start_row = 10){
  T_11.01 <- read.xlsx(workbook, sheet = "Table11.03", startRow = start_row)
  T_11.01 <- T_11.01[c("V1", "V2", "V3", "V5", "V6", "V8", "V9", "V11", "V12", "V14", "V15")]
  tmp <- c("HH Cars", "Sub-mode", "Access mode", "Model_E", "Survey_E",
           "Model_NB", "Survey_NB", "Model_B", "Survey_B", "Project_B", "survey2_B")
  colnames(T_11.01) <- tmp
  T_11.01 <- T_11.01[4:nrow(T_11.01),]
  T_11.01 <- T_11.01 %>% mutate_all(function(y) str_squish(y))
  T_11.01 <-subset(T_11.01, !(T_11.01$`HH Cars` %in% ""  ))
  T_11.01 <-subset(T_11.01, !(T_11.01$`Sub-mode` %in% c("------------------ -", 
                                                        "================== =", 
                                                        ". . . . . . . . . .")))
  T_11.01 <-subset(T_11.01, !(T_11.01$Survey_E %in% c("-------", 
                                                      "=======", 
                                                      ". . . .")))
  
  T_11.01 <- T_11.01 %>% mutate_at(.vars = colnames(T_11.01)[4:ncol(T_11.01)],
                                   function(y) as.numeric(y))
  return(T_11.01)
}


Get_11.04 <- function(workbook, start_row = 10){
  T_11.01 <- read.xlsx(workbook, sheet = "Table11.04", startRow = start_row)
  T_11.01 <- T_11.01[c("V1", "V2", "V3", "V5", "V6", "V8", "V9", "V11", "V12", "V14", "V15")]
  tmp <- c("HH Cars", "Sub-mode", "Access mode", "Model_E", "Survey_E",
           "Model_NB", "Survey_NB", "Model_B", "Survey_B", "Project_B", "survey2_B")
  colnames(T_11.01) <- tmp
  T_11.01 <- T_11.01[4:nrow(T_11.01),]
  T_11.01 <- T_11.01 %>% mutate_all(function(y) str_squish(y))
  T_11.01 <-subset(T_11.01, !(T_11.01$`HH Cars` %in% ""  ))
  T_11.01 <-subset(T_11.01, !(T_11.01$`Sub-mode` %in% c("------------------ -", 
                                                        "================== =", 
                                                        ". . . . . . . . . .")))
  T_11.01 <-subset(T_11.01, !(T_11.01$Survey_E %in% c("-------", 
                                                      "=======", 
                                                      ". . . .")))
  
  T_11.01 <- T_11.01 %>% mutate_at(.vars = colnames(T_11.01)[4:ncol(T_11.01)],
                                   function(y) as.numeric(y))
  return(T_11.01)
}


Get_12.01 <- function(workbook, start_row = 10){
  tbl <- read.xlsx(workbook, sheet = "Table12.01", startRow = start_row)
  tmp <- c("District", "CTPP_Workers", "CTPP_Emplymnt", "MPO_POP_CTPP", "MPO_Pop_E", "MPO_Pop_NB", "MPO_Pop_B",
           "MPO_EMP_CTPP", "MPO_EMP_E", "MPO_EMP_NB", "MPO_EMP_B")
  colnames(tbl) <- tmp
  tbl <- tbl[6:(nrow(tbl)-2),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}


Get_2.04 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table2.04", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  #tbl[] <- lapply(tbl, function(x) if(is.character(x) || is.factor(x)) gsub("-", "_", x) else x)
  return(tbl)
}


Get_2.05 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table2.05", startRow = start_row)
  #tbl <- tbl[2:nrow(tbl),]
  #colnames(tbl)[1] <- "Station_group"
  #tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  colnames(tbl) <- c("Station_group",1:(ncol(tbl)-1))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}


Get_4.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table4.01", startRow = start_row)
  # print(tbl)
  # stop()
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}


Get_6.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table6.01", startRow = start_row)
  # print(tbl)
  # stop()
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}


Get_13.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table13.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}


Get_13.07 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table13.07", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}


Get_13.08 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table13.08", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_282.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table282.01", startRow = start_row)
  # print(tbl)
  # stop()
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_333.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table333.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_337.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table337.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_341.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table341.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_344.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table344.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_345.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table345.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}

Get_349.01 <- function(workbook=Extracted_Tables, start_row = 11){
  tbl <- read.xlsx(workbook, sheet = "Table349.01", startRow = start_row)
  tbl <- tbl[2:nrow(tbl),]
  tbl <- tbl %>% mutate_all(function(y) str_squish(y))
  tbl <- tbl %>% mutate_at(.vars = colnames(tbl)[2:ncol(tbl)],
                           function(y) as.numeric(y))
  return(tbl)
}




Get_OtherInfo <- function(STOPS_Results_file){
  STOPS_data <- read.delim(STOPS_Results_file, skipNul = TRUE, quote = "")
  #print("end- here")
  STOPS_data <- rbind(colnames(STOPS_data), STOPS_data)
  colnames(STOPS_data) <- "STOPS_REPORT"
  L <- c()
  L[length(L)+1] <- which(grepl("STOPS Mode:",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Base Year:                  ",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Access Walk Weight              ",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Boarding Penalty:              ",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Auto Time Factor",STOPS_data$STOPS_REPORT))[2]
  L[length(L)+1] <- which(grepl("PNR Density multiplier",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("KNR usage adjustment",STOPS_data$STOPS_REPORT))
  #L[length(L)+1] <- which(grepl("Station group calibration",STOPS_data$STOPS_REPORT))
  #print(L)
  L[length(L)+1] <- ifelse(length(which(grepl("station/stop and route group calibration",STOPS_data$STOPS_REPORT))) %in% 0,
                              "station/stop and route group calibration N/A", which(grepl("station/stop and route group calibration",STOPS_data$STOPS_REPORT)))
  L[length(L)+1] <- which(grepl("District-level calibration",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("FG Constant Discount",STOPS_data$STOPS_REPORT))[1]
  L[length(L)+1] <- which(grepl("FG Constant Discount",STOPS_data$STOPS_REPORT))[2]
  L[length(L)+1] <- which(grepl("Raw linked transit trips:",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Raw unlinked transit trips:",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Target unlinked transit trips:",STOPS_data$STOPS_REPORT))
  L[length(L)+1] <- which(grepl("Regional calibration:",STOPS_data$STOPS_REPORT))
  
  df <- STOPS_data[L, ]
  return(df)
}

