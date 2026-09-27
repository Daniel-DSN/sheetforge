.PHONY: install test demo clean

install:
	pip install -r requirements.txt

test:
	PYTHONPATH=src python3 -m pytest -q

demo:
	@mkdir -p demo
	@{ echo "$$ python -m sheetforge.cli clean samples/messy.csv -o demo/out.xlsx --report demo/bad.csv --summary demo/summary.md"; \
		PYTHONPATH=src python3 -m sheetforge.cli clean samples/messy.csv -o demo/out.xlsx --report demo/bad.csv --summary demo/summary.md; \
		echo "[exit] $$?"; } > demo/demo_run1.txt 2>&1
	@{ echo "$$ python -m sheetforge.cli summarize demo/out.xlsx --by city --agg order_value --func sum --out demo/city_report.md"; \
		PYTHONPATH=src python3 -m sheetforge.cli summarize demo/out.xlsx --by city --agg order_value --func sum --out demo/city_report.md; \
		echo "[exit] $$?"; \
		echo ""; \
		echo "$$ python -m sheetforge.cli summarize demo/out.xlsx --by city --agg order_value --func avg"; \
		PYTHONPATH=src python3 -m sheetforge.cli summarize demo/out.xlsx --by city --agg order_value --func avg; \
		echo "[exit] $$?"; } > demo/demo_run2.txt 2>&1
	@{ echo "$$ python -m sheetforge.cli merge samples/messy.csv samples/messy_b.csv -o demo/merged.csv --key email"; \
		PYTHONPATH=src python3 -m sheetforge.cli merge samples/messy.csv samples/messy_b.csv -o demo/merged.csv --key email; \
		echo "[exit] $$?"; } > demo/demo_merge.txt 2>&1
	@echo "--- demo_run1.txt ---"
	@cat demo/demo_run1.txt
	@echo "--- demo_run2.txt ---"
	@cat demo/demo_run2.txt
	@echo "--- demo_merge.txt ---"
	@cat demo/demo_merge.txt

clean:
	rm -f demo/out.xlsx demo/bad.csv demo/summary.md demo/city_report.md demo/merged.csv
	rm -f demo/demo_run1.txt demo/demo_run2.txt demo/demo_merge.txt
	find . -name __pycache__ -type d -exec rm -rf {} +
