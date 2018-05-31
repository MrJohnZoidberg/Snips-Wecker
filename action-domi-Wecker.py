#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import ConfigParser
import io
import paho.mqtt.client as mqtt
import json
from alarmclock import AlarmClock

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"


class SnipsConfigParser(ConfigParser.SafeConfigParser):
    def to_dict(self):
        return {section: {option_name: option for option_name, option in self.items(section)} for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding=CONFIGURATION_ENCODING_FORMAT) as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, ConfigParser.Error) as e:
        return dict()


conf = read_configuration_file(CONFIG_INI)
print("Conf:", conf)

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
        elif intentname == 'isAlarm':
            is_alarm, response = alarmclock.is_alarm(slots)
            if is_alarm == 1:
                say(session_id, response)
            else:
                alarmclock.wanted_intents = ['domi:isAlarmConfirmNew']
                dialogue(session_id, response, alarmclock.wanted_intents)
        elif intentname == 'isAlarmConfirmNew':
            if intentname in alarmclock.wanted_intents:
                alarmclock.wanted_intents = []
                say(session_id, alarmclock.set(alarmclock.slots))
            else:
                say(session_id, "")
        elif intentname == 'deleteAlarm':
            say(session_id, alarmclock.delete_alarm(slots))
        elif intentname == 'deleteAlarmsDateTry':
            alarms, response = alarmclock.delete_date_try(slots)
            if alarms == 0:
                say(session_id, response)
            else:
                alarmclock.wanted_intents = ['domi:deleteAlarmsDateConfirm']
                dialogue(session_id, response, alarmclock.wanted_intents)
        elif intentname == 'deleteAlarmsDateConfirm':
            if intentname in alarmclock.wanted_intents:
                alarmclock.wanted_intents = []
                say(session_id, alarmclock.delete_date(slots))
            else:
                say(session_id, "")
        elif intentname == 'deleteAlarmsAllTry':
            number = alarmclock.delete_all_try()
            if number == 0:
                say(session_id, "Es sind keine Alarme gestellt.")
            elif number == 1:
                alarmclock.wanted_intents = ['domi:deleteAlarmsAllConfirm']
                dialogue(session_id, "Es ist ein Alarm aktiv. Bist du dir sicher?", alarmclock.wanted_intents)
            else:
                alarmclock.wanted_intents = ['domi:deleteAlarmsAllConfirm']
                dialogue(session_id,
                         "In der nächsten Zeit gibt es {num} Alarme. Bist du dir sicher?".format(num=number),
                         alarmclock.wanted_intents)
        elif intentname == 'deleteAlarmsAllConfirm':
            alarmclock.wanted_intents = []
            say(session_id, alarmclock.delete_all(slots))
        elif intentname == 'getAlarmsAll':
            say(session_id, alarmclock.get_all())


def say(session_id, text):
    mqtt_client.publish('hermes/dialogueManager/endSession',
                        json.dumps({'text': text, "sessionId": session_id}))


def dialogue(session_id, text, intent_filter):
    mqtt_client.publish('hermes/dialogueManager/continueSession',
                        json.dumps({'text': text, "sessionId": session_id, "intentFilter": intent_filter}))


if __name__ == "__main__":
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect("localhost", "1883")
    alarmclock = AlarmClock(conf)
    mqtt_client.loop_forever()
