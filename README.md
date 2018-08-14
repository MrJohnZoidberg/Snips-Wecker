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

JSON Payload:

| Key | Value |
|-----|-------|
|new|*JSON Object* - Alarm details: datetime object and siteId (see below: 'new')|
|all|*Dictionary* - Includes all alarms (see below: 'all')|

'new' - JSON Object:

| Key | Value |
|-----|-------|
|datetime|*String* - Python object which includes date and time|
|siteId|*String* - Site where the user created the alarm|

'all' - Dictionary:

| Dict-Keys (description) | Dict-Values (description)|
|-----|-------|
|datetime (*String* - Includes date and time; can be parsed into `datetime` object with `strptime` from module `datetime`)|siteId (*String* - Site where the user created the alarm)|

Example parsing:
```python
datetimeobj = datetime.datetime.strptime(data['new']['datetime'], "%Y-%m-%d %H:%M")
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
