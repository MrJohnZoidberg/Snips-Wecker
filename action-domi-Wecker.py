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
            slot_dict[slot['slotName']] = slot['value']
        elif slot['value']['kind'] == "TimeInterval":
            slot_dict[slot['slotName']] = slot['value']
    # TODO: Manage empty slots dict (wrong types)
    return slot_dict


def on_message_intent(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    session_id = data['sessionId']
    intent_id = data['intent']['intentName']

    if intent_id == user_intent('newAlarm'):
        slots = get_slots(data)
        say(session_id, alarmclock.new_alarm(slots, data['siteId']))

    elif intent_id == user_intent('getAlarms'):
        slots = get_slots(data)
        say(session_id, alarmclock.get_alarms(slots, data['siteId']))

    elif intent_id == user_intent('deleteAlarms'):
        slots = get_slots(data)
        say(session_id, alarmclock.delete_alarms_try(slots, data['siteId']))

    elif intent_id == user_intent('deleteAlarmSingle'):
        slots = get_slots(data)
        say(session_id, alarmclock.delete_single(slots))

    elif intent_id == user_intent('deleteAlarmsMulti'):
        slots = get_slots(data)
        multi_alarms, response = alarmclock.delete_multi_try(slots, data['siteId'])
        if multi_alarms:
            alarmclock.confirm_intents[data['siteId']] = {'past_intent': intent_id,
                                                          'alarms': multi_alarms}
            dialogue(session_id, response, [user_intent('confirmAlarm')])
        else:
            say(session_id, response)

    elif intent_id == user_intent('confirmAlarm'):
        confirm_data = alarmclock.confirm_intents[data['siteId']]
        if confirm_data and 'past_intent' in confirm_data.keys():
            past_data = alarmclock.confirm_intents[data['siteId']]
            slots = get_slots(data)
            if slots['answer']['value'] == "yes":
                if past_data['past_intent'] == user_intent('deleteAlarmsMulti'):
                        result = alarmclock.delete_alarms(past_data['alarms'])
                        if result['rc'] == 0:
                            say(session_id, "Erledigt.")
                        else:
                            say(session_id, "Es ist ein Fehler aufgetreten.")
            else:
                say(session_id, "Abgebrochen.")
            alarmclock.confirm_intents[data['siteId']] = None


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
    restore_alarms = alarmclock.utils.get_restorestat(conf)
    ringtone_status = alarmclock.utils.get_ringtonestat(conf)
    alarmclock = AlarmClock(ringtone_wav, ringing_timeout, dict_siteid, default_room, restore_alarms, ringtone_status)
    mqtt_client = mqtt.Client()
    mqtt_client.message_callback_add('hermes/intent/#', on_message_intent)
    mqtt_client.connect("localhost", "1883")
    mqtt_client.subscribe('hermes/intent/#')
    mqtt_client.loop_forever()
