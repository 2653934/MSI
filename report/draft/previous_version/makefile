file=report

ifeq ($(OS),Windows_NT)
PDFLATEX ?= "$(LOCALAPPDATA)/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe"
BIBTEX ?= "$(LOCALAPPDATA)/Programs/MiKTeX/miktex/bin/x64/bibtex.exe"
else
PDFLATEX ?= pdflatex
BIBTEX ?= bibtex
endif

all:
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(file).tex
	$(BIBTEX) $(file)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(file).tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(file).tex

ifeq ($(OS),Windows_NT)
clean:
	-cmd /C del /Q $(file).aux $(file).bbl $(file).blg $(file).log $(file).out $(file).synctex.gz 2>NUL
	-cmd /C del /Q $(file).toc $(file).lof $(file).lot 2>NUL
	-cmd /C del /Q sections\*.aux 2>NUL
else
clean:
	rm -f $(file).aux $(file).bbl $(file).blg $(file).log $(file).out $(file).synctex.gz
	rm -f $(file).toc $(file).lof $(file).lot
	rm -f sections/*.aux
endif
