# Snips-Wecker ⏰
A skill for Snips.ai with a fully controllable alarm clock.

## Features

- Full multi-room support
- context-awareness: it detects what room you're in
- default room (if you don't say a room in your command)
- customizable (ringtone sound, volume, ringing timeout, rooms)
- no system command for the ringtone used, all realized with the Snips platform

## Installation

**Important:** The following instructions assume that [Snips](https://snips.gitbook.io/documentation/snips-basics) is
already configured and running on your device. [SAM](https://snips.gitbook.io/getting-started/installation) should
also already be set up and connected to your device and your account.

1. In the German [skill store](https://console.snips.ai/) add the
skill `Wecker & Alarme` (by domi; [this] to
your *German* assistant.

2. If you already have the same assistant on your platform, update it
(with [Sam](https://snips.gitbook.io/getting-started/installation)) with:
      ```bash
      sam update-assistant
      ```
      
   Otherwise install the assistant on the platform with [Sam](https://snips.gitbook.io/getting-started/installation)
   with the following command to choose it (if you have multiple assistants in your Snips console):
      ```bash
      sam install assistant
      ```
      
4. You will be asked to fill some parameters with values.
The following should explain these parameters:
    - With the parameter `bbbb` you can set the maximum length of all the fortunes,
so that no very long fortune cookies are read out. The default is 100 characters.
    - The value in `bbbb` controls the number of repetitions of the Question
    "Noch ein Spruch?" if the answer was not understood. The default is one repetition.
    
5. If you want to change the values again, you can run:
      ```bash
      sam install skills
      ```
   The command will only update the skills, not the whole assistant.

## Usage

### Example sentences



### While ringing

While an alarm is ringing you can say a hotword, which is by default "Hey Snips!".

![img](resources/Snips-Alarmclock-ringing.png)

### MQTT messages

#### In messages

##### hermes/external/alarmclock/stopringing

JSON Payload (I'm working on it):

| Key | Value |
|-----|-------|
|siteId	| *String* - Site where the alarmclock should stop ringing|

#### Out messages

##### external/alarmclock/newalarm

JSON Payload: `data` (example access name)

| Key | Value |
|-----|-------|
|new|*JSON Object* - Alarm details: datetime object and siteId (see below: 'new')|
|all|*Dictionary* - Includes all alarms (with the new one; see below: 'all')|

'new' - JSON Object: `data['new']`

| Key | Value |
|-----|-------|
|datetime|*String* - Python object which includes date and time|
|siteId|*String* - Site where the user created the alarm|

'all' - Dictionary: `data['all']`

| Dict-Keys (description) | Dict-Values (description)|
|-----|-------|
|datetime (*String* - Includes date and time; can be parsed into `datetime` object with `strptime` from module `datetime` (see below))|siteId (*String* - Site where the user created the alarm)|

Example parsing:
```python
import json
import datetime
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    mqttc.subscribe('external/alarmclock/newalarm')
    
def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    dt = datetime.datetime
    # parsing of string to datetime object
    dt_newalarm = dt.strptime(data['new']['datetime'], "%Y-%m-%d %H:%M")
    # dictionary with all alarms
    alarms_dict = {dt.strptime(dtstr, "%Y-%m-%d %H:%M"): data['all'][dtstr] for dtstr in data['all']}
    # [...]

mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect(host='localhost', port=1883)
mqttc.loop_forever()

```

**external/alarmclock/ringing**

JSON Payload:

| Key | Value |
|-----|-------|
|siteId|*String* - Site where the alarmclock is ringing|

## Todo
- README
- Store alarms after creating new one
- Ringing in threads (multiple alarms at the same time)
- subscribe intents only to single confirm, not listen to all
- Send alarm data over MQTT
- Publish app in the snips console app store


## Contribution

Please report errors (you can see them with `sam service log`) and bugs by
opening a [new issue](https://github.com/MrJohnZoidberg/Snips-Wecker/issues/new).
You can also write other ideas for this skill. Thank you for your contribution.
