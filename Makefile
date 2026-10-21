PY ?= python
export PYTHONPATH := src

.PHONY: all evaluate report test calibrate clean

all: test evaluate report

evaluate:
	$(PY) -m packrisk.evaluate

report:
	$(PY) -m packrisk.report

test:
	$(PY) tests/run_tests.py

# make calibrate USAID=data/raw/usaid_scms.csv [DATACO=data/raw/DataCoSupplyChainDataset.csv]
calibrate:
	$(PY) -m packrisk.calibrate --usaid $(USAID) $(if $(DATACO),--dataco $(DATACO),)

clean:
	rm -rf outputs/powerbi/*.csv outputs/figures/*.png outputs/*.csv outputs/*.json RESULTS.md
