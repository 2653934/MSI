file=proposal
file2=lit-review

all:
	pdflatex $(file).tex
	bibtex $(file)
	pdflatex $(file).tex
	pdflatex $(file).tex

lr:
	pdflatex $(file2).tex
	bibtex $(file2)
	pdflatex $(file2).tex
	pdflatex $(file2).tex
	rm -rf $(file2).{aux,bbl,blg,lof,log,lot,out,synctex.gz,toc}

clean:
	rm -rf $(file).{aux,bbl,blg,lof,log,lot,out,synctex.gz,toc}
	rm -rf $(file2).{aux,bbl,blg,lof,log,lot,out,synctex.gz,toc}
