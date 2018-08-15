# Snips-Wecker ⏰
A skill for Snips.ai with a fully controllable alarm clock.

## Installation

## Usage

### Example sentences

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
    alarms_dict = {dt.strptime(dtstr, "%Y-%m-%d %H:%M"): data['all'][dtstr] for dtstr in data['all'].keys()}
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

## TODO
- README
- Store alarms after creating new one
- Ringing in threads (multiple alarms at the same time)
- subscribe intents only to single confirm, not listen to all
- Send alarm data over MQTT
- Publish app in the snips console app store
