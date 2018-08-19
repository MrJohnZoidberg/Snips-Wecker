#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
import ConfigParser
import io
from alarmclock.alarmclock import AlarmClock
import alarmclock.utils

USERNAME_INTENTS = "domi"


def user_intent(intentname):
    return USERNAME_INTENTS + ":" + intentname


class SnipsConfigParser(ConfigParser.SafeConfigParser):
    def to_dict(self):
        return {section: {
            option_name: option for option_name, option in self.items(section)
        } for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding="utf-8") as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, ConfigParser.Error):
        return dict()


def get_slots(data):
    slot_dict = {}
    for slot in data['slots']:
        if slot['value']['kind'] in ["InstantTime", "Custom"]:
            slot_dict[slot['slotName']] = slot['value']['value']
        elif slot['value']['kind'] == "TimeInterval":
            slot_dict[slot['slotName']] = slot['value']['from']
    return slot_dict


def on_message_intent(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    session_id = data['sessionId']
    intent_id = data['intent']['intentName']

    if intent_id == user_intent('newAlarm'):
            slots = get_slots(data)
            result = alarmclock.new_alarm(slots, data['siteId'])
            if result['rc'] == 0:
                response = "Der Wecker wird {future_part} um {h} Uhr {min} {room_part} klingeln.".format(
                    future_part=result['fpart'], h=result['hours'], min=result['minutes'], room_part=result['rpart'])
            elif result['rc'] == 1:
                response = "Dieser Raum wurde noch nicht eingestellt. Bitte schaue in der Anleitung " \
                           "von dieser Wecker-Äpp nach, wie man Räume hinzufügen kann."
            elif result['rc'] == 2:
                response = "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von " \
                           "dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.".format(room=result['room'])
            elif result['rc'] == 3:
                response = "Diese Zeit liegt in der Vergangenheit. Bitte stelle einen anderen Alarm."
            elif result['rc'] == 4:
                response = "Dieser Alarm würde jetzt klingeln. Bitte stelle einen anderen Alarm."
            else:
                response = "Es ist ein Fehler aufgetreten."
            say(session_id, response)

    elif intent_id == user_intent('getAlarmsDate'):
        slots = get_slots(data)
        result = alarmclock.get_on_date(slots, data['siteId'])
        if result['rc'] == 0:
            if len(result['alarms']) > 1:
                response = "{f_part} gibt es {num} Alarme. ".format(f_part=result['future_part'],
                                                                    num=len(result['alarms']))
                for details_dict in result['alarms']:
                    response += "einen {room_part} um {h} Uhr {min}".format(room_part=details_dict['room_part'],
                                                                              h=details_dict['hours'],
                                                                              min=details_dict['minutes'])
                    if details_dict != result['alarms'][-1]:
                        response += ", "
                    else:
                        response += "."
                    if details_dict == result['alarms'][-2]:
                        response += "und "
                response += "."
            elif len(result['alarms']) == 1:
                response = "{f_part} gibt es einen Alarm {room_part} um {h} Uhr {min}.".format(
                    f_part=result['future_part'], room_part=result['alarms'][0]['room_part'],
                    h=result['alarms'][0]['hours'], min=result['alarms'][0]['minutes'])
            else:
                response = "{f_part} gibt es keinen Alarm.".format(f_part=result['future_part'])
        elif result['rc'] == 1:
            response = "Dieser Tag liegt in der Vergangenheit."
        else:
            response = "Es ist ein Fehler aufgetreten."
        say(session_id, response)

    elif intent_id == user_intent('getAlarmsAll'):
        say(session_id, alarmclock.get_all())

    elif intent_id == user_intent('isAlarm'):
        slots = get_slots(data)
        result = alarmclock.is_alarm(slots, data['siteId'])
        if result['is_alarm']:
            say(session_id, "Ja, {f_part} wird ein Alarm um {h} Uhr {min} {r_part} klingeln.".format(
                f_part=result['future_part'], h=result['hours'], min=result['minutes'], r_part=result['room_part']))
        else:
            response = "Nein, zu dieser Zeit ist kein Alarm gestellt. Möchtest du {f_part} um {h} Uhr {min} einen " \
                       "Wecker {r_part} stellen?".format(f_part=result['future_part'], h=result['hours'],
                                                         min=result['minutes'], r_part=result['room_part'])
            alarmclock.wanted_intents = [user_intent('isAlarmConfirmNew')]
            dialogue(session_id, response, alarmclock.wanted_intents)

    elif intent_id == user_intent('isAlarmConfirmNew'):
        if intent_id in alarmclock.wanted_intents:
            # TODO: Connect wanted_intents with siteid
            alarmclock.wanted_intents = []
            say(session_id, alarmclock.new_alarm(alarmclock.remembered_slots, data['siteId']))

    elif intent_id == user_intent('deleteAlarm'):
        slots = get_slots(data)
        say(session_id, alarmclock.delete_alarm(slots))

    elif intent_id == user_intent('deleteAlarmsDateTry'):
        slots = get_slots(data)
        alarms, response = alarmclock.delete_date_try(slots)
        if alarms:
            alarmclock.wanted_intents = [user_intent('deleteAlarmsDateConfirm')]
            dialogue(session_id, response, alarmclock.wanted_intents)
        else:
            say(session_id, response)

    elif intent_id == user_intent('deleteAlarmsDateConfirm'):
        if intent_id in alarmclock.wanted_intents:
            alarmclock.wanted_intents = []
            slots = get_slots(data)
            say(session_id, alarmclock.delete_date(slots))
        else:
            end(session_id)

    elif intent_id == user_intent('deleteAlarmsAllTry'):
        alarms, response = alarmclock.delete_all_try()
        if alarms:
            alarmclock.wanted_intents = [user_intent('deleteAlarmsAllConfirm')]
            dialogue(session_id, response, alarmclock.wanted_intents)
        else:
            say(session_id, response)

    elif intent_id == user_intent('deleteAlarmsAllConfirm'):
        if user_intent('deleteAlarmsAllConfirm') in alarmclock.wanted_intents:
            alarmclock.wanted_intents = []
            slots = get_slots(data)
            say(session_id, alarmclock.delete_all(slots))


def end(session_id):
    mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({"sessionId": session_id}))


def say(session_id, text):
    mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({'text': text, "sessionId": session_id}))


def dialogue(session_id, text, intent_filter):
    mqtt_client.publish('hermes/dialogueManager/continueSession',
                        json.dumps({'text': text, "sessionId": session_id, "intentFilter": intent_filter}))


if __name__ == "__main__":
    conf = read_configuration_file("config.ini")
    ringtone_wav = alarmclock.utils.edit_volume("alarm-sound.wav", alarmclock.utils.get_ringvol(conf))
    ringing_timeout = alarmclock.utils.get_ringtmo(conf)
    dict_siteid = alarmclock.utils.get_dsiteid(conf)
    print("dict_siteid: ", dict_siteid)
    default_room = alarmclock.utils.get_dfroom(conf)
    alarmclock = AlarmClock(ringtone_wav, ringing_timeout, dict_siteid, default_room)
    mqtt_client = mqtt.Client()
    mqtt_client.message_callback_add('hermes/intent/#', on_message_intent)
    mqtt_client.connect("localhost", "1883")
    mqtt_client.subscribe('hermes/intent/#')
    mqtt_client.loop_forever()
