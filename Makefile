PY ?= python
export PYTHONPATH := src

.PHONY: all evaluate sensitivity report test calibrate clean

all: test evaluate sensitivity report

evaluate:
	$(PY) -m packrisk.evaluate

sensitivity:
	$(PY) -m packrisk.sensitivity

report:
	$(PY) -m packrisk.report

test:
	$(PY) tests/run_tests.py

# make calibrate USAID=data/raw/usaid_scms.csv [DATACO=data/raw/DataCoSupplyChainDataset.csv]
calibrate:
	$(PY) -m packrisk.calibrate --usaid $(USAID) $(if $(DATACO),--dataco $(DATACO),)

clean:
	rm -rf outputs/powerbi/*.csv outputs/figures/*.png outputs/*.csv outputs/*.json RESULTS.md
