# Research report working draft

This directory is the editable report workspace. The official supplied files
remain unchanged in `../Template/`.

## Structure

- `report.tex`: IEEE-style entry point and report metadata;
- `sections/`: modular section drafts;
- `images/`: the pipeline diagram and selected current-evidence figures;
- `references.bib`: bibliography copied from the proposal and extended for the
  VAE and Integrated Gradients methods.

## Compile

From this directory, use:

```bash
make
```

The Makefile automatically uses the current user's standard MiKTeX location on
Windows and the commands available on `PATH` on Linux. The equivalent manual
sequence is:

```bash
pdflatex report.tex
bibtex report
pdflatex report.tex
pdflatex report.tex
```

The draft was compiled with MiKTeX and inspected page by page on 2026-09-22.
The build currently produces a clean six-page PDF. This is shorter than the
final 8--12-page requirement because the scientific framing is intentionally
being held as a provisional draft until the supervision discussion on
2026-09-28.

## Draft status

The abstract, introduction, related work, methodology, results, discussion and
conclusion contain an evidence-grounded first draft. They are not final prose.
In particular, the revised research questions are a provisional framing for
discussion with Hairong on 2026-09-28, not an approved departure from the
proposal. Supervisor confirmation, primary-source bibliography verification, a
compact hyperparameter table and the code-availability statement remain
outstanding.
