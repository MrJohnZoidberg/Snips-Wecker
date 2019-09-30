BIN = $(PWD)/.venv3/bin
GETTEXT = /usr/local/opt/gettext

POT = alarmclock/locales/messages.pot
LOCALE = alarmclock/locales/de/LC_MESSAGES/messages.po

run: .venv3 $(LOCALE:.po=.mo)
	PYTHONPATH=$(PWD)/../snipsclient $(BIN)/python3 action-domi-Wecker.py

.venv3: requirements.txt
	[ -d $@ ] || python3 -m venv $@
	$(BIN)/pip3 install -r $<
	touch $@

messages: $(POT)

$(POT): alarmclock/alarmclock.py alarmclock/alarm.py alarmclock/translation.py
	$(GETTEXT)/bin/xgettext -L python -o $@ $^

%.mo: %.po
	$(GETTEXT)/bin/msgfmt -o $@ $<
