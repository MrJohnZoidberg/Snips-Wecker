#!/usr/bin/env bash -e

VENV=venv

if [ ! -d "$VENV" ]
then

    PYTHON=`which python2`

    if [ ! -f $PYTHON ]
    then
        echo "could not find python"
    fi
    virtualenv -p $PYTHON $VENV

fi

. $VENV/bin/activate

pip install -r requirements.txt

if [ ! -e ./.saved_alarms.json ]; then
    touch .saved_alarms.json
    sudo chown _snips-skills .saved_alarms.json
fi

if [ ! -e ./.temporary_ringtone ]; then
    touch .temporary_ringtone
    sudo chown _snips-skills .temporary_ringtone
fi

if [ -f /usr/share/snips/assistant/snippets/domi.Alarme_\&_Wecker/config.ini ]
then
    cp /usr/share/snips/assistant/snippets/domi.Alarme_\&_Wecker/config.ini config.ini
else
    cp config.ini.default config.ini
fi
