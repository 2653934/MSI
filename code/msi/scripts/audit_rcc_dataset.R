#!/usr/bin/env Rscript

# Read-only inspection of the CardinalWorkflows RCC dataset. No spectra or
# derived labels are written; only compact audit tables go into the project.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  stop("Usage: Rscript scripts/audit_rcc_dataset.R ARCHIVE OUTPUT_DIRECTORY")
}
archive <- args[[1L]]
output_dir <- args[[2L]]
if (!file.exists(archive)) stop("Archive does not exist: ", archive)
main <- function() {
scratch <- tempfile("rcc-audit-")
dir.create(scratch)
on.exit(unlink(scratch, recursive = TRUE), add = TRUE)
member <- "CardinalWorkflows/data/rcc.rda"
utils::untar(archive, files = member, exdir = scratch)
data_file <- file.path(scratch, member)
if (!file.exists(data_file)) stop("RCC data member could not be extracted")

env <- new.env(parent = globalenv())
loaded <- load(data_file, envir = env)
if (!("rcc" %in% loaded)) stop("rcc object is not present in rcc.rda")
if (requireNamespace("Cardinal", quietly = TRUE)) {
  suppressPackageStartupMessages(library(Cardinal))
  data <- as(env$rcc, "MSImagingExperiment")
  coordinates <- as.data.frame(Cardinal::coord(data))
  runs <- as.character(Cardinal::run(data))
  diagnosis <- as.character(data$diagnosis)
  size <- dim(data)
  mz_values <- as.numeric(Cardinal::mz(data))
  extraction_mode <- "Cardinal MSImagingExperiment"
} else {
  # The archive stores a legacy MSImageSet. Its AnnotatedDataFrame metadata
  # slots can be read without constructing or converting a Cardinal model.
  cat("Cardinal is unavailable; reading serialized metadata slots only.\n")
  pixel_data <- methods::slot(methods::slot(env$rcc, "pixelData"), "data")
  feature_data <- methods::slot(methods::slot(env$rcc, "featureData"), "data")
  required_pixel <- c("x", "y", "run", "diagnosis")
  if (!all(required_pixel %in% names(pixel_data))) {
    stop("Missing pixel metadata columns. Available: ", paste(names(pixel_data), collapse = ", "))
  }
  if (!("mz" %in% names(feature_data))) {
    stop("Missing m/z metadata column. Available: ", paste(names(feature_data), collapse = ", "))
  }
  coordinates <- pixel_data[c("x", "y")]
  runs <- as.character(pixel_data$run)
  diagnosis <- as.character(pixel_data$diagnosis)
  size <- c(nrow(feature_data), nrow(pixel_data))
  mz_values <- as.numeric(feature_data$mz)
  extraction_mode <- "legacy MSImageSet metadata slots (no Cardinal)"
}
if (!all(c("x", "y") %in% names(coordinates))) {
  stop("Coordinates do not have x and y columns")
}
if (nrow(coordinates) != length(runs) || length(runs) != length(diagnosis)) {
  stop("Spectrum, coordinate, run, and diagnosis counts differ")
}
if (length(size) != 2L || size[[2L]] != nrow(coordinates)) {
  stop("Unexpected feature-by-spectrum dimensions")
}
if (length(mz_values) != size[[1L]] || anyNA(mz_values)) {
  stop("Unexpected or missing m/z axis")
}
if (anyNA(coordinates$x) || anyNA(coordinates$y) || anyNA(runs)) {
  stop("Coordinates or run IDs contain missing values")
}

pixel <- data.frame(
  run = runs,
  x = coordinates$x,
  y = coordinates$y,
  diagnosis = diagnosis,
  stringsAsFactors = FALSE
)
run_names <- sort(unique(pixel$run))
run_rows <- lapply(run_names, function(name) {
  part <- pixel[pixel$run == name, , drop = FALSE]
  width <- max(part$x) - min(part$x) + 1
  height <- max(part$y) - min(part$y) + 1
  labelled <- !is.na(part$diagnosis)
  data.frame(
    run = name,
    spectra = nrow(part),
    unique_coordinates = nrow(unique(part[c("x", "y")])),
    x_min = min(part$x), x_max = max(part$x),
    y_min = min(part$y), y_max = max(part$y),
    grid_pixels = width * height,
    grid_coverage_percent = 100 * nrow(part) / (width * height),
    labelled_pixels = sum(labelled),
    unlabelled_pixels = sum(!labelled),
    cancer_pixels = sum(part$diagnosis == "cancer", na.rm = TRUE),
    normal_pixels = sum(part$diagnosis == "normal", na.rm = TRUE),
    other_labels = paste(setdiff(unique(part$diagnosis[labelled]), c("cancer", "normal")), collapse = ";"),
    stringsAsFactors = FALSE
  )
})
run_summary <- do.call(rbind, run_rows)

label_rows <- lapply(run_names, function(name) {
  part <- pixel[pixel$run == name & !is.na(pixel$diagnosis), , drop = FALSE]
  labels <- sort(unique(part$diagnosis))
  if (!length(labels)) return(NULL)
  do.call(rbind, lapply(labels, function(label) {
    region <- part[part$diagnosis == label, , drop = FALSE]
    data.frame(
      run = name, diagnosis = label, pixels = nrow(region),
      x_min = min(region$x), x_max = max(region$x),
      y_min = min(region$y), y_max = max(region$y),
      stringsAsFactors = FALSE
    )
  }))
})
label_summary <- do.call(rbind, label_rows)

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
write.csv(run_summary, file.path(output_dir, "run_summary.csv"), row.names = FALSE)
write.csv(label_summary, file.path(output_dir, "label_region_summary.csv"), row.names = FALSE)

cat("Cardinal RCC audit\n")
cat("Extraction mode:", extraction_mode, "\n")
cat("Features (m/z values):", size[[1L]], "\n")
cat("m/z range:", min(mz_values), "to", max(mz_values), "\n")
cat("Spectra:", size[[2L]], "\n")
cat("Runs:", length(run_names), "\n")
cat("Diagnosis counts (including NA):\n")
print(table(pixel$diagnosis, useNA = "ifany"))
cat("\nPer-run audit:\n")
print(run_summary, row.names = FALSE)
cat("\nPer-label coordinate extents:\n")
print(label_summary, row.names = FALSE)
cat("\nCaution: diagnosis is a tissue/sample annotation, not a verified pixel-level tumour boundary.\n")
cat("Saved compact audit tables in:", output_dir, "\n")
}

main()
