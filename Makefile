BIN = $(PWD)/.venv3/bin
GETTEXT = /usr/local/opt/gettext
export PATH := $(PATH):$(GETTEXT)/bin

LOCALE = alarmclock/locales/de/LC_MESSAGES/alarmclock.mo

run: .venv3
	PYTHONPATH=$(PWD)/../snipsclient $(BIN)/python3 action-domi-Wecker.py

.venv3: requirements.txt
	[ -d $@ ] || python3 -m venv $@
	$(BIN)/pip3 install -r $<
	touch $@

messages: alarmclock/locales/messages.pot
	
alarmclock/locales/messages.pot: alarmclock/alarmclock.py alarmclock/alarm.py
	pygettext.py -d messages -o $@ alarmclock/alarm.py alarmclock/alarmclock.py

locale: $(LOCALE)

%.mo: %.po
	msgfmt -o $@ $<
