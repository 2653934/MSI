#!/usr/bin/env Rscript
# Item D (supervisor chat 2026-10-15 13:00 and 15:35): RCC feasibility, go/no-go.
# Runs inside Slurm in the separate rcc_env (Cardinal), never in s3pl_env.
#   Rscript scripts/rcc_feasibility_export.R RCC_RDA EXPORT_DIR REPORT_JSON
# Criterion 2: rcc.rda loads. Criterion 3: pixel-level class labels per run.
# Exports one HDF5 per run in the project contract (Data pixels x m/z, mzArray,
# xLocation, yLocation from 1, Class_Label 0..K-1 by sorted label level) for the
# criterion-4 audit. Labels are exported for evaluation only, as on GBM/CAC.
# Writes a JSON report; no model, clustering or peak scoring.
suppressPackageStartupMessages({
  library(jsonlite)
  library(rhdf5)
})
`%||%` <- function(a, b) if (is.null(a)) b else a
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) stop("Usage: rcc_feasibility_export.R RCC_RDA EXPORT_DIR REPORT_JSON")
rda <- args[[1L]]; export_dir <- args[[2L]]; report_path <- args[[3L]]
report <- list(status = "failed", criteria = list(), runs = list(),
               r_version = R.version.string)

env <- new.env()
loaded <- load(rda, envir = env)
if (!("rcc" %in% loaded)) stop("rcc object not present in rcc.rda")
object <- env$rcc
report$object_class <- class(object)[[1L]]
report$criteria$loads <- TRUE

cardinal <- requireNamespace("Cardinal", quietly = TRUE)
report$cardinal_version <- if (cardinal) as.character(utils::packageVersion("Cardinal")) else NA
extract <- NULL
if (cardinal) {
  suppressPackageStartupMessages(library(Cardinal))
  experiment <- tryCatch(
    if (is(object, "MSImagingExperiment")) object else as(object, "MSImagingExperiment"),
    error = function(e) { report$cardinal_conversion_error <<- conditionMessage(e); NULL })
  if (!is.null(experiment)) {
    pdata <- as.data.frame(Cardinal::pixelData(experiment))
    extract <- list(
      path = "Cardinal MSImagingExperiment",
      mz = as.numeric(Cardinal::mz(experiment)),
      x = as.integer(Cardinal::coord(experiment)$x),
      y = as.integer(Cardinal::coord(experiment)$y),
      run = as.character(Cardinal::run(experiment)),
      pdata = pdata,
      intensity = function(columns) as.matrix(Cardinal::spectra(experiment)[, columns, drop = FALSE]))
  }
}
if (is.null(extract)) {
  # Legacy MSImageSet slots, read without Cardinal model code.
  pixel <- methods::slot(methods::slot(object, "pixelData"), "data")
  feature <- methods::slot(methods::slot(object, "featureData"), "data")
  image <- methods::slot(methods::slot(object, "imageData"), "data")
  values <- image[["iData"]]
  extract <- list(path = "legacy MSImageSet slots", mz = as.numeric(feature$mz),
                  x = as.integer(pixel$x), y = as.integer(pixel$y),
                  run = as.character(pixel$sample %||% pixel$run), pdata = pixel,
                  intensity = function(columns) as.matrix(values[, columns, drop = FALSE]))
}
report$extraction_path <- extract$path
report$pixels <- length(extract$x)
report$mz_bins <- length(extract$mz)
report$mz_range <- range(extract$mz)
report$pixel_metadata_columns <- names(extract$pdata)
label_column <- intersect(c("diagnosis", "Diagnosis", "class", "label"), names(extract$pdata))
if (length(label_column) == 0L) {
  report$criteria$pixel_labels <- FALSE
  report$reason <- "no pixel-level class column (diagnosis/class/label) in the pixel metadata"
  write_json(report, report_path, auto_unbox = TRUE, pretty = TRUE, digits = NA)
  quit(status = 0)
}
labels <- as.character(extract$pdata[[label_column[[1L]]]])
levels <- sort(unique(labels[!is.na(labels)]))
report$label_column <- label_column[[1L]]
report$label_levels <- levels
report$label_encoding <- setNames(as.list(seq_along(levels) - 1L), levels)
dir.create(export_dir, recursive = TRUE, showWarnings = FALSE)
labelled_runs <- 0L
for (run in sort(unique(extract$run))) {
  columns <- which(extract$run == run)
  run_labels <- labels[columns]
  counts <- as.list(table(factor(run_labels, levels = levels), useNA = "no"))
  missing <- sum(is.na(run_labels))
  record <- list(run = run, pixels = length(columns), label_counts = counts,
                 unlabelled_pixels = missing,
                 classes_present = sum(unlist(counts) > 0))
  values <- extract$intensity(columns)            # m/z x pixels
  record$finite <- all(is.finite(values))
  record$nonnegative <- all(values >= 0, na.rm = TRUE)
  if (missing == 0L && record$classes_present >= 2L) labelled_runs <- labelled_runs + 1L
  if (missing == 0L && record$finite && record$nonnegative) {
    x <- extract$x[columns] - min(extract$x[columns]) + 1L
    y <- extract$y[columns] - min(extract$y[columns]) + 1L
    order <- order(y, x)
    file <- file.path(export_dir, paste0("RCC_", gsub("[^A-Za-z0-9_]+", "_", run), ".h5"))
    if (file.exists(file)) stop("refusing to overwrite ", file)
    h5createFile(file)
    h5write(t(values[, order, drop = FALSE]), file, "Data")   # stored as m/z x pixels on disk
    h5write(extract$mz, file, "mzArray")
    h5write(as.numeric(x[order]), file, "xLocation")
    h5write(as.numeric(y[order]), file, "yLocation")
    h5write(as.numeric(match(run_labels[order], levels) - 1L), file, "Class_Label")
    record$export <- file
  }
  report$runs[[length(report$runs) + 1L]] <- record
}
report$runs_with_two_or_more_label_classes_and_no_unlabelled_pixels <- labelled_runs
report$criteria$pixel_labels <- labelled_runs >= 4L
report$status <- "complete"
write_json(report, report_path, auto_unbox = TRUE, pretty = TRUE, digits = NA)
cat("RCC feasibility export complete\n")
