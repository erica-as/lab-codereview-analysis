.PHONY: all report clean

all: report

report:
	python3 src/analysis/descriptive_stats.py
	python3 src/analysis/correlation_analysis.py
	python3 src/analysis/generate_figures.py
	python3 src/analysis/generate_tables.py
	cd report && pdflatex main.tex
	cd report && pdflatex main.tex

clean:
	rm -f report/*.aux report/*.log report/*.out report/*.toc
