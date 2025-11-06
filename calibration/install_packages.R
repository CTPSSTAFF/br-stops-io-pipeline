required_repo <- 'https://cloud.r-project.org'
options(repos = c(CRAN = required_repo))

cran_packages <- c(
  'dplyr',
  'data.table',
  'foreign',
  'iotools',
  'janitor',
  'openxlsx',
  'stringr',
  'zeallot',
  'scales',
  'knitr',
  'rmarkdown',
  'future',
  'future.apply',
  'progress',
  'readr',
  'ggplot2',
  'htmltools',
  'kableExtra',
  'leaflet',
  'measurements',
  'reactable',
  'reshape2',
  'rstudioapi',
  'RColorBrewer',
  'tidyverse',
  'rmdformats',
  'remotes'
)

installed <- rownames(installed.packages())
missing_cran <- setdiff(cran_packages, installed)
if (length(missing_cran) > 0) {
  message('Installing CRAN packages: ', paste(missing_cran, collapse = ', '))
  install.packages(missing_cran)
} else {
  message('All CRAN packages already installed.')
}

# rgdal has been archived on CRAN; install from the bundled binary if needed
if (!requireNamespace('rgdal', quietly = TRUE)) {
  rgdal_zip <- file.path('reports', 'Summary_HTML_Report', 'rgdal.zip')
  if (file.exists(rgdal_zip)) {
    message('Installing rgdal from local zip: ', rgdal_zip)
    install.packages(rgdal_zip, repos = NULL, type = 'win.binary')
  } else {
    warning('rgdal package is missing and reports/Summary_HTML_Report/rgdal.zip was not found.')
  }
} else {
  message('rgdal already installed.')
}

# RStudioConsoleRender lives on GitHub
if (!requireNamespace('RStudioConsoleRender', quietly = TRUE)) {
  message('Installing RStudioConsoleRender from GitHub (requires Rtools on Windows).')
  if (!requireNamespace('remotes', quietly = TRUE)) {
    install.packages('remotes')
  }
  remotes::install_github('jeffjjohnston/RStudioConsoleRender', upgrade = 'never')
} else {
  message('RStudioConsoleRender already installed.')
}
