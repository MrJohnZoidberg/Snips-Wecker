#!/usr/bin/env bash -e

sudo rm -rf /var/lib/snips/skills/.config
sudo rm -rf /var/lib/snips/skills/.mplayer

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

if [ ! -f ./.mplayer_pipe ]; then
    touch .mplayer_pipe
    sudo chown _snips-skills .mplayer_pipe
fi
