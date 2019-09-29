BIN = $(PWD)/.venv3/bin

run: .venv3
	PYTHONPATH=$(PWD)/../snipsclient $(BIN)/python3 action-domi-Wecker.py

.venv3: requirements.txt
	[ -d $@ ] || python3 -m venv $@
	$(BIN)/pip3 install -r $<
	touch $@
