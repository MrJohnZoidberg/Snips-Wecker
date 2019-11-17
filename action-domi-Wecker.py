#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import json
import alarmclock as alarm_clock
import toml
USERNAME_INTENTS = "domi"
MQTT_BROKER_ADDRESS = "localhost:1883"
MQTT_USERNAME = None
MQTT_PASSWORD = None
LANGUAGE = "de-DE"


def add_prefix(intent_name):
    return USERNAME_INTENTS + ":" + intent_name


def get_slots(data):
    slot_dict = {}
    try:
        for slot in data['slots']:
            if slot['value']['kind'] in ["InstantTime", "TimeInterval", "Duration"]:
                slot_dict[slot['slotName']] = slot['value']
            elif slot['value']['kind'] == "Custom":
                slot_dict[slot['slotName']] = slot['value']['value']
    except (KeyError, TypeError, ValueError):
        slot_dict = {}
    return slot_dict


def msg_new_alarm(*args):
    # create new alarm with the given properties
    data = json.loads(args[2].payload.decode())
    slots = get_slots(data)
    end_session(args[0], data['sessionId'], alarmclock.new_alarm(slots, data['siteId']))


def msg_get_alarms(*args):
    # say alarms with the given properties
    data = json.loads(args[2].payload.decode())
    slots = get_slots(data)
    end_session(args[0], data['sessionId'], alarmclock.get_alarms(slots, data['siteId']))


def msg_get_next_alarm(*args):
    # say next alarm
    data = json.loads(args[2].payload.decode())
    slots = get_slots(data)
    end_session(args[0], data['sessionId'], alarmclock.get_next_alarm(slots, data['siteId']))


def msg_get_missed_alarms(*args):
    # say missed alarms with the given properties
    data = json.loads(args[2].payload.decode())
    slots = get_slots(data)
    end_session(args[0], data['sessionId'], alarmclock.get_missed_alarms(slots, data['siteId']))


def msg_delete_alarms(*args):
    # delete alarms with the given properties
    data = json.loads(args[2].payload.decode())
    slots = get_slots(data)
    end_session(args[0], data['sessionId'], alarmclock.delete_alarms(slots, data['siteId']))


def end_session(client, session_id, text=None):
    if text:
        payload = {'text': text, 'sessionId': session_id}
    else:
        payload = {'sessionId': session_id}
    client.publish('hermes/dialogueManager/endSession', json.dumps(payload))


def dialogue(session_id, text, intent_filter, custom_data=None):
    data = {'text': text,
            'sessionId': session_id,
            'intentFilter': intent_filter}
    if custom_data:
        data['customData'] = json.dumps(custom_data)
    mqtt_client.publish('hermes/dialogueManager/continueSession', json.dumps(data))


def on_connect(*args):
    client = args[0]
    client.message_callback_add('hermes/intent/' + add_prefix('newAlarm'), msg_new_alarm)
    client.message_callback_add('hermes/intent/' + add_prefix('getAlarms'), msg_get_alarms)
    client.message_callback_add('hermes/intent/' + add_prefix('getNextAlarm'), msg_get_next_alarm)
    client.message_callback_add('hermes/intent/' + add_prefix('getMissedAlarms'), msg_get_missed_alarms)
    client.message_callback_add('hermes/intent/' + add_prefix('deleteAlarms'), msg_delete_alarms)
    client.subscribe('hermes/intent/#')


if __name__ == "__main__":
    snips_config = toml.load('/etc/snips.toml')
    if 'mqtt' in snips_config['snips-common'].keys():
        MQTT_BROKER_ADDRESS = snips_config['snips-common']['mqtt']
    if 'mqtt_username' in snips_config['snips-common'].keys():
        MQTT_USERNAME = snips_config['snips-common']['mqtt_username']
    if 'mqtt_password' in snips_config['snips-common'].keys():
        MQTT_PASSWORD = snips_config['snips-common']['mqtt_password']

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.connect(MQTT_BROKER_ADDRESS.split(":")[0], int(MQTT_BROKER_ADDRESS.split(":")[1]))
    alarmclock = alarm_clock.AlarmClock(mqtt_client)
    mqtt_client.loop_forever()
