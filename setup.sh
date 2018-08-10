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

if [ ! -f ./.saved_alarms ]; then
    touch .saved_alarms
    sudo chown _snips-skills .saved_alarms
fi

if [ -d /usr/lib/python2.7/dist-packages/pygame ]; then
    cp -r /usr/lib/python2.7/dist-packages/pygame ./venv/lib/python2.7/site-packages/
fi
