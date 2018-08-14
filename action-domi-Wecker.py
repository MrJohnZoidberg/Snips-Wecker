#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
from alarmclock.utils import read_configuration_file
from alarmclock.alarmclock import AlarmClock

USERNAME_INTENTS = "domi"


def user_intent(intentname):
    return USERNAME_INTENTS + ":" + intentname


def get_slots(data):
    return {slot['slotName']: slot['value']['value'] for slot in data['slots']}


def on_message_intent(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    session_id = data['sessionId']
    intent_id = data['intent']['intentName']

    if intent_id == user_intent('newAlarm'):
        for slot in data['slots']:
            print("slot:", slot['slotName'])
            print("Going deeper...")
            print("kind:", slot['value']['kind'])
            for value in slot['value']:
                print("value:", value)
        try:
            slots = get_slots(data)
            say(session_id, alarmclock.set(slots))
        except:
            print("Error")

    elif intent_id == user_intent('getAlarmsDate'):
        slots = get_slots(data)
        say(session_id, alarmclock.get_on_date(slots))

    elif intent_id == user_intent('isAlarm'):
        slots = get_slots(data)
        is_alarm, response = alarmclock.is_alarm(slots)
        if is_alarm == 1:
            say(session_id, response)
        else:
            alarmclock.wanted_intents = [user_intent('isAlarmConfirmNew')]
            dialogue(session_id, response, alarmclock.wanted_intents)

    elif intent_id == user_intent('isAlarmConfirmNew'):
        if intent_id in alarmclock.wanted_intents:
            alarmclock.wanted_intents = []
            say(session_id, alarmclock.set(alarmclock.remembered_slots))

    elif intent_id == user_intent('deleteAlarm'):
        slots = get_slots(data)
        say(session_id, alarmclock.delete_alarm(slots))

    elif intent_id == user_intent('deleteAlarmsDateTry'):
        slots = get_slots(data)
        alarms, response = alarmclock.delete_date_try(slots)
        if alarms == 0:
            say(session_id, response)
        else:
            alarmclock.wanted_intents = [user_intent('deleteAlarmsDateConfirm')]
            dialogue(session_id, response, alarmclock.wanted_intents)

    elif intent_id == user_intent('deleteAlarmsDateConfirm'):
        if intent_id in alarmclock.wanted_intents:
            alarmclock.wanted_intents = []
            slots = get_slots(data)
            say(session_id, alarmclock.delete_date(slots))
        else:
            say(session_id, "")

    elif intent_id == user_intent('deleteAlarmsAllTry'):
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

    elif intent_id == user_intent('deleteAlarmsAllConfirm'):
        if 'domi:deleteAlarmsAllConfirm' in alarmclock.wanted_intents:
            alarmclock.wanted_intents = []
            slots = get_slots(data)
            say(session_id, alarmclock.delete_all(slots))
    elif intent_id == user_intent('getAlarmsAll'):
        say(session_id, alarmclock.get_all())


def end(session_id):
    mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({"sessionId": session_id}))


def say(session_id, text):
    mqtt_client.publish('hermes/dialogueManager/endSession',
                        json.dumps({'text': text, "sessionId": session_id}))


def dialogue(session_id, text, intent_filter):
    mqtt_client.publish('hermes/dialogueManager/continueSession',
                        json.dumps({'text': text, "sessionId": session_id, "intentFilter": intent_filter}))


if __name__ == "__main__":
    conf = read_configuration_file("config.ini")
    alarmclock = AlarmClock(conf)
    mqtt_client = mqtt.Client()
    mqtt_client.message_callback_add('hermes/intent/#', on_message_intent)
    mqtt_client.connect("localhost", "1883")
    mqtt_client.subscribe('hermes/intent/#')
    mqtt_client.loop_forever()
