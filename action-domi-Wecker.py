#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import ConfigParser
import io
import paho.mqtt.client as mqtt
import json
from alarmclock import AlarmClock

USERNAME_INTENTS = "domi"


class SnipsConfigParser(ConfigParser.SafeConfigParser):
    def to_dict(self):
        return {section: {option_name: option for option_name, option in self.items(section)} for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding="utf-8") as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, ConfigParser.Error) as e:
        return dict()


conf = read_configuration_file("config.ini")


def user_intent(intentname):
    return USERNAME_INTENTS + ":" + intentname


# MQTT client to connect to the bus
mqtt_client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    client.subscribe('hermes/intent/#')
    client.subscribe('hermes/hotword/default/detected')


def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if alarmclock.ringing == 1:
        if msg.topic == 'hermes/hotword/default/detected':
            alarmclock.stop()
    else:
        if 'sessionId' not in data.keys():  # if 'hermes/hotword/default/detected'
            return
        session_id = data['sessionId']
        intentId = data['intent']['intentName']

        if intentId == user_intent('newAlarm'):
            slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
            say(session_id, alarmclock.set(slots))
        elif intentId == user_intent('getAlarmsDate'):
            slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
            say(session_id, alarmclock.get_on_date(slots))
        elif intentId == user_intent('isAlarm'):
            slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
            is_alarm, response = alarmclock.is_alarm(slots)
            if is_alarm == 1:
                say(session_id, response)
            else:
                alarmclock.wanted_intents = [user_intent('isAlarmConfirmNew')]
                dialogue(session_id, response, alarmclock.wanted_intents)
        elif intentId == user_intent('isAlarmConfirmNew'):
            if intentId in alarmclock.wanted_intents:
                alarmclock.wanted_intents = []
                say(session_id, alarmclock.set(alarmclock.remembered_slots))
        elif intentId == user_intent('deleteAlarm'):
            slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
            say(session_id, alarmclock.delete_alarm(slots))
        elif intentId == user_intent('deleteAlarmsDateTry'):
            slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
            alarms, response = alarmclock.delete_date_try(slots)
            if alarms == 0:
                say(session_id, response)
            else:
                alarmclock.wanted_intents = [user_intent('deleteAlarmsDateConfirm')]
                dialogue(session_id, response, alarmclock.wanted_intents)
        elif intentId == user_intent('deleteAlarmsDateConfirm'):
            if intentId in alarmclock.wanted_intents:
                alarmclock.wanted_intents = []
                slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
                say(session_id, alarmclock.delete_date(slots))
            else:
                say(session_id, "")
        elif intentId == user_intent('deleteAlarmsAllTry'):
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
        elif intentId == user_intent('deleteAlarmsAllConfirm'):
            alarmclock.wanted_intents = []
            slots = {slot['slotName']: slot['value']['value'] for slot in data['slots']}
            say(session_id, alarmclock.delete_all(slots))
        elif intentId == user_intent('getAlarmsAll'):
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
