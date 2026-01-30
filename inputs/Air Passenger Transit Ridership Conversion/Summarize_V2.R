rm(list=ls())
library(vroom)
library(dplyr)
library(stringr)

# 1) Work in current folder (or setwd("...") to another)
dir <- getwd()
message("Current directory: ", dir)
setwd(dir)

# 2) Grab ONLY the *_selected.csv files
files <- list.files(pattern = "_full\\.csv$")
message("Files ending with '_full.csv':")
print(files)

# Initialize an empty list to store data frames
Total_Trips <- 0

# Step 4 and 5: Process each file and perform full join
for (file in files) {
  # Extract name1 and name2 from the filename
  parts <- strsplit(file, "_")[[1]]
  name1 <- parts[3]
  name2 <- parts[4]
  
  # Read the CSV file
  df <- vroom(file, col_names = FALSE, show_col_types = FALSE)
  # Conditional column naming
  if (name1 == "lx") {
    # Special case: only 3 columns
    colnames(df) <- c("Rows", "Columns", "lx")
  } else {
    # General case: full set of 8 columns
    colnames(df) <- c("Rows", "Columns", "dp", "pu", "tw", "ta", "lx", "rs")
  }
  
  df[is.na(df)] <- 0
  
  # select non zero records in df
  df <- df[rowSums(df[, -c(1, 2), drop = FALSE]) > 0, ]
  
  # Change column names for all columns except the first two
  col_names <- colnames(df)
  col_names[-(1:2)] <- paste(name1, name2, col_names[-(1:2)], sep = "_")
  colnames(df) <- col_names
  
  # Print the sum of all columns except the first two
  sums <- colSums(df[, -c(1, 2), drop = FALSE])
  print(paste("Sum of columns in", file, ":"))
  print(sums)
  
  Total_Trips <- Total_Trips + sum(sums)
  
  # Add the dataframe to the list
  #data_frames[[file]] <- df
  
  if(file == files[1]){
    result_df <- df
  } else {
    result_df <- Reduce(function(x, y) merge(x, y, all = TRUE), list(result_df, df))
  }
  
  rm(df)
}

result_df[is.na(result_df)] <- 0

# Add a column that is the sum of all columns except the first two
result_df$total_sum <- rowSums(result_df[, -c(1, 2)])

result_df$HBW <- result_df$resb_pk_ta + result_df$resb_pk_tw + result_df$resl_pk_ta + result_df$resl_pk_tw  + 
                  result_df$visb_pk_ta + result_df$visb_pk_tw + result_df$visl_pk_ta + result_df$visl_pk_tw 
result_df$HBO <- result_df$resb_np_ta + result_df$resb_np_tw + result_df$resl_np_ta + result_df$resl_np_tw 
result_df$NHB <- result_df$visb_np_ta + result_df$visb_np_tw + result_df$visl_np_ta + result_df$visl_np_tw

Air_trips <- result_df[,c("Rows", "Columns", "HBW", "HBO", "NHB")]
colnames(Air_trips)[1:2] <- c("O", "D")

# Optional: Write the result to a new CSV file if needed
write.csv(result_df, "full_joined_output.csv", row.names = FALSE)
write.csv(Air_trips, "AirPassengerTrips_Transit_TDMZones.csv", row.names = FALSE)


#Read TAZ lookup file
TAZ_lookup <- vroom(paste0(dir, "/MPO_TAZ_SE.csv"))
TAZ_lookup <- TAZ_lookup[c("taz_id", "TAZ")]

#Read TAZ lookup file
A2_STOPS_Eq <- read.csv(paste0(dir, "/A2_STOPS_PATH_MPO-CTPP_Equiv.csv"), header = FALSE)

lookup <- A2_STOPS_Eq %>% left_join(TAZ_lookup, by=c("V2" = "TAZ"))

joined_data <- lookup %>% left_join(Air_trips, by = c("taz_id" = "O" )) # %>% subset(! is.na(D))
joined_data$D <- 185
joined_data[is.na(joined_data)] <- 0

joined_data$HBW_adj <- round(joined_data$HBW * joined_data$V3, 2)
joined_data$HBO_adj <- round(joined_data$HBO * joined_data$V3, 2)
joined_data$NHB_adj <- round(joined_data$NHB * joined_data$V3, 2)


Airport_Summary <- joined_data %>% group_by(V1, D) %>%
  summarise(HBW = sum(HBW_adj),
            HBO = sum(HBO_adj),
            NHB = sum(NHB_adj))
colnames(Airport_Summary) <- c("O", "D", "HBW", "HBO", "NHB")
Airport_Summary$HBW[Airport_Summary$O %in% "25025~2413C "  ] <- Airport_Summary$HBW[Airport_Summary$O %in% "25025~2413C "  ] + 
  Airport_Summary$HBW[Airport_Summary$O %in% "25025$2413A "  ]
Airport_Summary$HBO[Airport_Summary$O %in% "25025~2413C "  ] <- Airport_Summary$HBO[Airport_Summary$O %in% "25025~2413C "  ] + 
  Airport_Summary$HBO[Airport_Summary$O %in% "25025$2413A "  ]
Airport_Summary$NHB[Airport_Summary$O %in% "25025~2413C "  ] <- Airport_Summary$NHB[Airport_Summary$O %in% "25025~2413C "  ] + 
  Airport_Summary$NHB[Airport_Summary$O %in% "25025$2413A "  ]

Airport_Summary <- Airport_Summary %>% subset(!(O %in% "25025$2413A "))
Airport_Summary$D <- "25025$2413A "

write.csv(Airport_Summary, paste0(dir,"\\AirPassengerTrips_Transit_intermediate.csv"), quote = FALSE, sep = ",", row.names = FALSE)

Airport_Summary$O <- sub(".*([$~])", "\\1", Airport_Summary$O)
Airport_Summary$D <- sub(".*([$~])", "\\1", Airport_Summary$D)

Airport_Summary$O <- sub(" ", "", Airport_Summary$O)
Airport_Summary$D <- sub(" ", "", Airport_Summary$D)


colnames(Airport_Summary) <- c("ProdZone", "AttrZone", "Curr-1car-HBW-Trn", "Curr-1car-HBO-Trn", "Curr-1car-NHB-Trn")


write.csv(Airport_Summary, "AirPassengerTrips_Transit.csv", quote = FALSE, sep = ",", row.names = FALSE)
