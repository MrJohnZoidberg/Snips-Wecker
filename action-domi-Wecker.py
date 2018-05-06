#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
from alarmclock import AlarmClock
import snipsDefaults as snips

with open('config.yaml') as config_file:
    config = yaml.load(config_file)

# MQTT client to connect to the bus
mqtt_client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    client.subscribe("hermes/intent/#")

def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if msg.topic == 'hermes/hotword/default/detected':
        if alarmclock.ringing == 1:
            alarmclock.stop()
    else:
        slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
        session_id = data['sessionId']
        user, intentname = data['intent']['intentName'].split(':')
        
        if intentname == 'newAlarm':
            say(session_id, alarmclock.set(slots))
        elif intentname == 'getAlarmsDate':
            say(session_id, alarmclock.get_on_date(slots))
            
        snips.previousIntent = msg

def say(session_id, text):
    mqtt_client.publish('hermes/dialogueManager/endSession',
                        json.dumps({'text': text, "sessionId": session_id}))
def dialogue(session_id, text, intent_filter):
    mqtt_client.publish('hermes/dialogueManager/continueSession',
                        json.dumps({'text': text, "sessionId": session_id, "intentFilter": intent_filter}))

if __name__ == "__main__":
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(snips.mqtt_host, snips.mqtt_port)
    alarmclock = AlarmClock(config)
    mqtt_client.loop_forever()
