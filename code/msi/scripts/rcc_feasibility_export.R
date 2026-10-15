#!/usr/bin/env Rscript
# Item D (supervisor chat 2026-10-15 13:00 and 15:35): RCC feasibility, go/no-go.
# Runs inside Slurm in the separate rcc_env (Cardinal), never in s3pl_env.
#   Rscript scripts/rcc_feasibility_export.R RCC_RDA EXPORT_DIR REPORT_JSON
# Criterion 2: rcc.rda loads. Criterion 3: a run counts as labelled when every
# annotated level (cancer, normal) has pixels; unlabelled (NA) pixels do not
# disqualify it. NA is kept as a third class "unannotated" (K = 3, every pixel
# kept so the grid stays intact), as CAC scores background (supervisor chat
# 2026-10-15 19:37, option (a), predeclared before any RCC export or score).
# Exports one HDF5 per run in the project contract (Data pixels x m/z, mzArray,
# xLocation, yLocation from 1, Class_Label 0..K-1: sorted annotated levels, then
# unannotated last) for the criterion-4 audit. Labels are exported for evaluation
# only, as on GBM/CAC. Also records, descriptively, where NA pixels lie and their
# TIC by class, to say whether NA is mainly off-tissue border or unannotated tissue.
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
annotated <- sort(unique(labels[!is.na(labels)]))
if ("unannotated" %in% annotated) stop("an annotated level is already called 'unannotated'")
labels[is.na(labels)] <- "unannotated"
levels <- c(annotated, "unannotated")
report$label_column <- label_column[[1L]]
report$annotated_levels <- annotated
report$label_levels <- levels
report$label_encoding <- setNames(as.list(seq_along(levels) - 1L), levels)
report$unlabelled_treatment <- "NA kept as third class 'unannotated' (chat 2026-10-15 19:37, option a)"

tic_summary <- function(tic) {
  if (length(tic) == 0L) return(list(pixels = 0L))
  list(pixels = length(tic), median = stats::median(tic), mean = mean(tic),
       q10 = unname(stats::quantile(tic, 0.10)), q90 = unname(stats::quantile(tic, 0.90)))
}
# Descriptive only: where the unannotated pixels lie on the run's measured grid.
na_location <- function(x, y, is_na) {
  key <- paste(x, y)
  measured <- key
  annotated_key <- key[!is_na]
  neighbours <- function(dx, dy) paste(x + dx, y + dy)
  shifts <- list(c(1L, 0L), c(-1L, 0L), c(0L, 1L), c(0L, -1L))
  touches_unmeasured <- Reduce(`|`, lapply(shifts, function(d) !(neighbours(d[1], d[2]) %in% measured)))
  touches_annotated <- Reduce(`|`, lapply(shifts, function(d) neighbours(d[1], d[2]) %in% annotated_key))
  on_box_edge <- x == min(x) | x == max(x) | y == min(y) | y == max(y)
  n <- sum(is_na)
  fraction <- function(v) if (n == 0L) NA else sum(v & is_na) / n
  list(unannotated_pixels = n,
       fraction_on_bounding_box_edge = fraction(on_box_edge),
       fraction_touching_unmeasured_grid = fraction(touches_unmeasured | on_box_edge),
       fraction_touching_annotated_pixel = fraction(touches_annotated))
}
dir.create(export_dir, recursive = TRUE, showWarnings = FALSE)
labelled_runs <- 0L
for (run in sort(unique(extract$run))) {
  columns <- which(extract$run == run)
  run_labels <- labels[columns]
  counts <- as.list(table(factor(run_labels, levels = levels), useNA = "no"))
  missing <- counts[["unannotated"]]
  annotated_present <- sum(unlist(counts[annotated]) > 0)
  record <- list(run = run, pixels = length(columns), label_counts = counts,
                 unlabelled_pixels = missing,
                 annotated_classes_present = annotated_present,
                 all_annotated_classes_present = annotated_present == length(annotated),
                 classes_present = sum(unlist(counts) > 0))
  values <- extract$intensity(columns)            # m/z x pixels
  record$finite <- all(is.finite(values))
  record$nonnegative <- all(values >= 0, na.rm = TRUE)
  tic <- colSums(values)
  record$tic_by_class <- lapply(setNames(levels, levels), function(l) tic_summary(tic[run_labels == l]))
  record$unannotated_location <- na_location(extract$x[columns], extract$y[columns],
                                             run_labels == "unannotated")
  if (record$all_annotated_classes_present) labelled_runs <- labelled_runs + 1L
  if (record$all_annotated_classes_present && record$finite && record$nonnegative) {
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
report$runs_with_all_annotated_classes <- labelled_runs
report$criteria$pixel_labels <- labelled_runs >= 4L
report$status <- "complete"
write_json(report, report_path, auto_unbox = TRUE, pretty = TRUE, digits = NA)
cat("RCC feasibility export complete\n")
