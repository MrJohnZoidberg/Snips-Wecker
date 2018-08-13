# Snips-Wecker ⏰
A skill for Snips.ai with a fully controllable alarm clock.

## Installation

## Usage

### Example sentences

### MQTT messages

#### In messages

**hermes/external/alarmclock/stopringing**

#### Out messages

**external/alarmlock/ringing**

JSON Payload:

| Key | Value |
|-----|-------|
|siteId|*String* - Site where the alarmclock is ringing|

## TODO
- README
- subscribe intents only to single confirm, not listen to all
- Send alarm data over MQTT
- Publish app in the snips console app store
