# Snips-Wecker ⏰
An app for [Snips.ai](https://snips.ai/) with a fully controllable alarm clock.

## Features

- Full multi-room support
- context-awareness: it detects what room you're in
- default room (if you don't say a room in your command)
- customizable (ringtone sound, volume, ringing timeout, rooms)
- no system command for the ringtone used, all realized with the Snips platform

## Quickstart

With a Raspberry Pi: (If you already have Snips on your Platform and an assistant installed, continue reading below)

1. Set up [Raspbian](https://www.raspberrypi.org/downloads/raspbian/) Stretch Lite on
your Raspberry Pi 3 from the [Snips Maker Kit](https://makers.snips.ai/kit/)

2. Install the [Snips platform](https://snips.gitbook.io/documentation/snips-basics) on it
using [SAM](https://snips.gitbook.io/getting-started/installation)

3. In the [Snips console](https://console.snips.ai/) (create an account if necessary) create a new German assistant,
add the app `Alarme & Wecker` to it and install this assistant using SAM: `sam install assistant`

4. Enjoy it!


## Installation

### Using SAM (recommended)

**Important:** The following instructions assume that [Snips](https://snips.gitbook.io/documentation/snips-basics) is
already configured and running on your device. [SAM](https://snips.gitbook.io/getting-started/installation) should
also already be set up and connected to your device and your account.

1. In the German [app store](https://console.snips.ai/) add the
app `Wecker & Alarme` (by domi; [this] to
your *German* assistant.

2. If you already have the same assistant on your platform, update it with:
      ```bash
      sam update-assistant
      ```
      
   Otherwise install the assistant on the platform with the following command to
   choose it (if you have multiple assistants in your Snips console):
      ```bash
      sam install assistant
      ```
    

### Manually (not recommended)

**Important:** The following instructions assume that [Snips](https://snips.gitbook.io/documentation/snips-basics) is
already configured and running on your device.

**Note:** Not tested yet!

1. In the German [app store](https://console.snips.ai/) add the
app `Wecker & Alarme` (by domi; [this] to
your *German* assistant.

2. Download the assistant package by clicking on "Deploy Assistant" and then on "[...] manually".

## Configuration

In the Snips console or manually in the file `/var/lib/snips/skills/Snips-Wecker/config.ini` you can change
some parameters that influence the behaviour of the alarm clock app:

| Parameter name | Default | Range | Description |
|----------------|---------|-------|-------------|
| ringing_volume | 50      | 0 - 100 | Volume of the ringtone |
| ringing_timeout| 30s     | 3s - infinit | Time in seconds for the ringing timeout |
| dict_site-id   | Schlafzimmer:default | no range | Important if you have a multi-room setup of Snips!<br/>These are pairs of room names and siteIds of these rooms. |
| default_room   | Schlafzimmer | no range | Important if you have a multi-room setup of Snips!<br/>Here must be the name of the room in which the alarm is to be set, if no room was said in the command. |

### Multi-room specific

#### Parameter dict_site-id

#### Parameter default_room

#### Examples of multi-room configurations

##### Example 1

## Usage

### Example sentences



### While ringing

While an alarm is ringing in a room you can say a hotword in this room, which is by default "Hey Snips!".
The ringtone

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
|room|*String* - Room name where the alarmclock is ringing|

## Coming soon...
- New setting: snooze en/disabled (then don't end session)
- Internationalisation
- Nice README
- Send alarm data over MQTT
- Ability to change the ringtone sound
- Maybe: periodical alarms (daily, weekly)
- Publish app in the snips console app store


## Contribution

Please report errors (you can see them with `sam service log snips-skill-server` or on the Pi
with `sudo tail -f /var/log/syslog`) and bugs by opening
a [new issue](https://github.com/MrJohnZoidberg/Snips-Wecker/issues/new).
You can also write other ideas for this app. Thank you for your contribution.

Made with 💙
