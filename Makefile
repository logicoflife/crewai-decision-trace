PYTHONPATH=src
PYTHON=.venv/bin/python3

.PHONY: demo demo_all verify test clean_out viewer build_viewer

demo:
	@if [ -z "$(PERSONA)" ]; then echo "Usage: make demo PERSONA=<movie_buff|sports_fan|foodie>"; exit 1; fi
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m dt_crewai_demo.cli demo --persona $(PERSONA)

demo_all:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m dt_crewai_demo.cli demo_all

verify:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m dt_crewai_demo.cli verify

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -q

clean_out:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m dt_crewai_demo.cli clean_out

build_viewer:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m dt_crewai_demo.cli build_viewer

viewer:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m streamlit run streamlit_viewer/app.py
