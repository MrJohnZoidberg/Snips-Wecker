#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import json
from alarmclock.alarmclock import AlarmClock
import alarmclock.utils
import toml
from snipsclient import Client


PREFIX = "domi:"
MQTT_BROKER_ADDRESS = "localhost:1883"
MQTT_USERNAME = None
MQTT_PASSWORD = None


mqtt_client = Client()
alarmclock = AlarmClock( mqtt_client)


def get_slots( payload):
    'Extract names / values from slots'
    slots = {}
    for slot in payload['slots']:
        if slot['value']['kind'] in ("InstantTime", "TimeInterval", "Duration"):
            slots[ slot['slotName']] = slot['value']
        elif slot['value']['kind'] == "Custom":
            slots[ slot['slotName']] = slot['value']['value']
    return slots


def on( intent, handler):
    'Register an intent handler'
    
    def wrapper( client, userdata, msg):
        reply = handler( get_slots( msg.payload), msg.payload['siteId'])
        client.end_session( msg.payload['sessionId'], reply)

    mqtt_client.on_intent( PREFIX + intent)( wrapper)


on( 'newAlarm', alarmclock.new_alarm)
on( 'getAlarms', alarmclock.get_alarms)
on( 'getNextAlarm', alarmclock.get_next_alarm)
on( 'getMissedAlarms', alarmclock.get_missed_alarms)
on( 'answerAlarm', alarmclock.answer_alarm)


@mqtt_client.on_intent( PREFIX + 'deleteAlarms')
def delete_alarms_try( client, userdata, msg):
    # delete alarms with the given properties
    slots = get_slots( msg.payload)
    alarms, response = alarmclock.delete_alarms_try( slots, msg.payload['siteId'])
    if alarms:
        client.continue_session( msg.payload['sessionId'], response,
            [PREFIX + 'confirmAlarm'], custom_data={
                'past_intent': PREFIX + 'deleteAlarms',
                'siteId': msg.payload['siteId'],
                'slots': slots})
    else:
        client.end_session( msg.payload['sessionId'], response)


@mqtt_client.on_intent( PREFIX + 'confirmAlarm')
def delete_alarms( client, userdata, msg):
    custom_data = json.loads( msg.payload['customData'])
    if custom_data and 'past_intent' in custom_data.keys():
        slots = get_slots( msg.payload)
        if slots.get('answer') == "yes" and \
                custom_data['past_intent'] == PREFIX + 'deleteAlarms':
            response = alarmclock.delete_alarms( custom_data['slots'], custom_data['siteId'])
            client.end_session( msg.payload['sessionId'], response)
        else:
            client.end_session( msg.payload['sessionId'])
        del alarmclock.alarmctl.temp_memory[msg.payload['siteId']]
