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

if [ ! -f ./.saved_alarms.json ]; then
    touch .saved_alarms.json
    sudo chown _snips-skills .saved_alarms.json
fi

if [ ! -f ./.temporary_ringtone ]; then
    touch .temporary_ringtone
    sudo chown _snips-skills .temporary_ringtone
fi

cp config.ini.default config.ini
