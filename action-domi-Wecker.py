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
                say(session_id, "Der Wecker wird {future_part} um {h} Uhr {min} {room_part} klingeln.".format(
                    future_part=result['fpart'], h=result['hours'], min=result['minutes'], room_part=result['rpart']))
            elif result['rc'] == 1:
                say(session_id, "Dieser Raum wurde noch nicht eingestellt. Bitte schaue in der Anleitung "
                                "von dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.")
            elif result['rc'] == 2:
                say(session_id, "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von "
                                "dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.".format(room=result['room']))
            elif result['rc'] == 3:
                say(session_id, "Diese Zeit liegt in der Vergangenheit. Bitte stelle einen anderen Alarm.")
            elif result['rc'] == 4:
                say(session_id, "Dieser Alarm würde jetzt klingeln. Bitte stelle einen anderen Alarm.")

    elif intent_id == user_intent('getAlarmsDate'):
        slots = get_slots(data)
        result = alarmclock.get_on_date(slots, data['siteId'])
        if result['rc'] == 0:
            if len(result['alarms']) > 1:
                response = "{f_part} gibt es {num} Alarme. ".format(
                    f_part=result['future_part'],
                    num=len(result['alarms']))
                for details_dict in result['alarms']:
                    response += "einen {room_part} um {h} Uhr {min}".format(
                        room_part=details_dict['room_part'],
                        h=details_dict['hours'],
                        min=details_dict['minutes'])
                    if details_dict != result['alarms'][-1]:
                        response += ", "
                    else:
                        response += "."
                    if details_dict == result['alarms'][-2]:
                        response += "und "
            elif len(result['alarms']) == 1:
                response = "{f_part} gibt es einen Alarm {room_part} um {h} Uhr {min}.".format(
                    f_part=result['future_part'], room_part=result['alarms'][0]['room_part'],
                    h=result['alarms'][0]['hours'], min=result['alarms'][0]['minutes'])
            else:
                response = "{f_part} gibt es keinen Alarm.".format(f_part=result['future_part'])
            say(session_id, response)
        elif result['rc'] == 1:
            say(session_id, "Dieser Tag liegt in der Vergangenheit.")
        else:
            say(session_id, "Es ist ein Fehler aufgetreten.")

    elif intent_id == user_intent('getAlarms'):
        slots = get_slots(data)
        result = alarmclock.get_alarms(slots, data['siteId'])
        if result['rc'] == 0:
            if len(result['alarms_sorted']) >= 6:
                response = "Es gibt {num} Alarme. Die nächsten sechs sind: ".format(num=len(result['alarms_sorted']))
                for alarm in result['alarms_sorted'][:6]:
                    response += "{future_part} um {h} Uhr {min} {room_part}".format(
                        room_part=result['alarms_dict'][alarm]['room_part'],
                        future_part=result['alarms_dict'][alarm]['future_part'],
                        h=result['alarms_dict'][alarm]['hours'],
                        min=result['alarms_dict'][alarm]['minutes'])
                    if alarm != result['alarms_sorted'][:6][-1]:
                        response += ", "
                    else:
                        response += "."
                    if alarm == result['alarms_sorted'][:6][-2]:
                        response += "und "
                say(session_id, response)
            elif 2 <= len(result['alarms_sorted']) <= 5:
                response = "Es gibt {num} Alarme. ".format(num=len(result['alarms']))
                for alarm in result['alarms_sorted']:
                    response += "einen {future_part} um {h} Uhr {min} {room_part}".format(
                        room_part=result['alarms_dict'][alarm]['room_part'],
                        future_part=result['alarms_dict'][alarm]['future_part'],
                        h=result['alarms_dict'][alarm]['hours'],
                        min=result['alarms_dict'][alarm]['minutes'])
                    if alarm != result['alarms_sorted'][-1]:
                        response += ", "
                    else:
                        response += "."
                    if alarm == result['alarms_sorted'][-2]:
                        response += "und "
                say(session_id, response)
            elif len(result['alarms_sorted']) == 1:
                say(session_id, "Es gibt {future_part} einen Alarm {room_part} um {h} Uhr {min}.".format(
                    room_part=result['alarms_dict'][result['alarms_sorted'][0]]['room_part'],
                    h=result['alarms_dict'][result['alarms_sorted'][0]]['hours'],
                    min=result['alarms_dict'][result['alarms_sorted'][0]]['minutes'],
                    future_part=result['alarms_dict'][result['alarms_sorted'][0]]['future_part']))
            else:
                say(session_id, "Es sind keine Alarme gestellt.")
        elif result['rc'] == 1:
            say(session_id, "Dieser Raum wurde noch nicht eingestellt. Bitte schaue in der Anleitung "
                            "von dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.")
        elif result['rc'] == 2:
            say(session_id, "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von "
                            "dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.".format(room=result['room']))
        elif result['rc'] == 3:
            say(session_id, "Diese Zeit liegt in der Vergangenheit. Bitte stelle einen anderen Alarm.")
        elif result['rc'] == 4:
            say(session_id, "Dieser Alarm würde jetzt klingeln. Bitte stelle einen anderen Alarm.")

    elif intent_id == user_intent('isAlarm'):
        slots = get_slots(data)
        result = alarmclock.is_alarm(slots, data['siteId'])
        if result['rc'] == 0:
            if result['is_alarm']:
                say(session_id, "Ja, {f_part} wird ein Alarm um {h} Uhr {min} {r_part} klingeln.".format(
                    f_part=result['future_part'], h=result['hours'], min=result['minutes'], r_part=result['room_part']))
            else:
                response = "Nein, zu dieser Zeit ist kein Alarm gestellt. Möchtest du {f_part} um {h} Uhr {min} " \
                           "einen Wecker {r_part} stellen?".format(f_part=result['future_part'], h=result['hours'],
                                                                   min=result['minutes'], r_part=result['room_part'])
                alarmclock.confirm_intents[data['siteId']] = {'past_intent': intent_id, 'slots': slots}
                dialogue(session_id, response, [user_intent('confirmAlarm')])
        elif result['rc'] == 1:
            say(session_id, "Dieser Raum wurde noch nicht eingestellt. Bitte schaue in der Anleitung "
                            "von dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.")
        elif result['rc'] == 2:
            say(session_id, "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von "
                            "dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.".format(room=result['room']))
        elif result['rc'] == 3:
            say(session_id, "Diese Zeit liegt in der Vergangenheit.")

    elif intent_id == user_intent('deleteAlarmSingle'):
        slots = get_slots(data)
        say(session_id, alarmclock.delete_single(slots))

    elif intent_id == user_intent('deleteAlarmsMulti'):
        slots = get_slots(data)
        result = alarmclock.delete_multi_try(slots, data['siteId'])
        if result['rc'] == 0:
            if len(result['matching_alarms']) == 1:
                alarmclock.confirm_intents[data['siteId']] = {'past_intent': intent_id,
                                                              'alarms': result['matching_alarms'],
                                                              'siteid': result['siteid']}
                dialogue(session_id, "Es gibt {future_part} {room_part} einen Alarm. Bist du dir sicher?".format(
                    future_part=result['future_part'], room_part=result['room_part']),
                         [user_intent('confirmAlarm')])
            elif len(result['matching_alarms']) > 1:
                alarmclock.confirm_intents[data['siteId']] = {'past_intent': intent_id,
                                                              'alarms': result['matching_alarms'],
                                                              'siteid': result['siteid']}
                dialogue(session_id, "Es gibt {future_part} {room_part} {num} Alarme. Bist du dir sicher?".format(
                    future_part=result['future_part'], room_part=result['room_part'],
                    num=len(result['matching_alarms'])), [user_intent('confirmAlarm')])
            else:
                say(session_id, "Es gibt {room_part} {future_part} keinen Alarm.".format(
                    room_part=result['room_part'], future_part=result['future_part']))
        elif result['rc'] == 1:
            say(session_id, "Dieser Raum wurde noch nicht eingestellt. Bitte schaue in der Anleitung "
                            "von dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.")
        elif result['rc'] == 2:
            say(session_id, "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von "
                            "dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.".format(room=result['room']))
        elif result['rc'] == 3:
            say(session_id, "Diese Zeit liegt in der Vergangenheit.")

    elif intent_id == user_intent('confirmAlarm'):
        if 'past_intent' in alarmclock.confirm_intents[data['siteId']].keys():
            past_data = alarmclock.confirm_intents[data['siteId']]
            slots = get_slots(data)
            if slots['answer'] == "yes":
                if past_data['past_intent'] == user_intent('deleteAlarmsMulti'):
                        result = alarmclock.delete_multi(past_data['alarms'], past_data['siteid'])
                        if result['rc'] == 0:
                            say(session_id, "Erledigt.")
                        else:
                            say(session_id, "Es ist ein fehler aufgetreten.")
                if past_data['past_intent'] == user_intent('isAlarm'):
                    result = alarmclock.new_alarm(past_data['slots'], data['siteId'])
                    if result['rc'] == 0:
                        say(session_id, "Der Wecker wird {future_part} um {h} Uhr {min} {room_part} klingeln.".format(
                            future_part=result['fpart'], h=result['hours'], min=result['minutes'],
                            room_part=result['rpart']))
                    elif result['rc'] == 4:
                        say(session_id, "Dieser Alarm würde jetzt klingeln. Bitte stelle einen anderen Alarm.")
            else:
                say(session_id, "Abgebrochen.")
            alarmclock.confirm_intents[data['siteId']] = None


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
    default_room = alarmclock.utils.get_dfroom(conf)
    alarmclock = AlarmClock(ringtone_wav, ringing_timeout, dict_siteid, default_room)
    mqtt_client = mqtt.Client()
    mqtt_client.message_callback_add('hermes/intent/#', on_message_intent)
    mqtt_client.connect("localhost", "1883")
    mqtt_client.subscribe('hermes/intent/#')
    mqtt_client.loop_forever()
