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
        return {section: {option_name: option for option_name, option in self.items(section)}
                for section in self.sections()}


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
        if slot['value']['kind'] in ["InstantTime", "TimeInterval", "Duration"]:
            slot_dict[slot['slotName']] = slot['value']
        elif slot['value']['kind'] == "Custom":
            slot_dict[slot['slotName']] = slot['value']['value']
    # TODO: Manage empty slots dict (wrong types)
    return slot_dict


def on_message_intent(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    session_id = data['sessionId']
    intent_id = data['intent']['intentName']

    if intent_id == user_intent('newAlarm'):
        # create new alarm with the given properties
        slots = get_slots(data)
        say(session_id, alarmclock.new_alarm(slots, data['siteId']))

    elif intent_id == user_intent('getAlarms'):
        # say alarms with the given properties
        slots = get_slots(data)
        say(session_id, alarmclock.get_alarms(slots, data['siteId']))

    elif intent_id == user_intent('getMissedAlarms'):
        # say missed alarms with the given properties
        slots = get_slots(data)
        say(session_id, alarmclock.get_missed(slots, data['siteId']))

    elif intent_id == user_intent('deleteAlarms'):
        # delete alarms with the given properties
        slots = get_slots(data)
        multi_alarms, response = alarmclock.delete_alarms_try(slots, data['siteId'])
        if multi_alarms:
            alarmclock.temp_memory[data['siteId']] = {'past_intent': intent_id,
                                                      'alarms': multi_alarms}
            dialogue(session_id, response, [user_intent('confirmAlarm')])
        else:
            say(session_id, response)

    elif intent_id == user_intent('confirmAlarm'):
        confirm_data = alarmclock.temp_memory[data['siteId']]
        if confirm_data and 'past_intent' in confirm_data.keys():
            past_data = alarmclock.temp_memory[data['siteId']]
            slots = get_slots(data)
            if slots['answer'] == "yes":
                if past_data['past_intent'] == user_intent('deleteAlarms'):
                        response = alarmclock.delete_alarms(past_data['alarms'])
                        say(session_id, response)
            else:
                end_session(session_id)
            alarmclock.temp_memory[data['siteId']] = None

    elif intent_id == user_intent('answerAlarm'):
        slots = get_slots(data)
        say(session_id, alarmclock.answer_alarm(slots, data['siteId']))


def on_session_ended(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if alarmclock.temp_memory[data['siteId']] and data['termination']['reason'] != "nominal":
        # if session was ended while confirmation process clean the past intent memory
        alarmclock.temp_memory[data['siteId']] = None


def say(session_id, text):
    mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({'text': text,
                                                                         'sessionId': session_id}))


def end_session(session_id):
    mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({'sessionId': session_id}))


def dialogue(session_id, text, intent_filter):
    mqtt_client.publish('hermes/dialogueManager/continueSession', json.dumps({'text': text,
                                                                              'sessionId': session_id,
                                                                              'intentFilter': intent_filter}))


if __name__ == "__main__":
    config = read_configuration_file("config.ini")
    alarmclock = AlarmClock(config)
    mqtt_client = mqtt.Client()
    mqtt_client.message_callback_add('hermes/intent/#', on_message_intent)
    mqtt_client.message_callback_add('hermes/dialogueManager/sessionEnded', on_session_ended)
    mqtt_client.connect("localhost", "1883")
    mqtt_client.subscribe('hermes/intent/#')
    mqtt_client.subscribe('hermes/dialogueManager/sessionEnded')
    mqtt_client.loop_forever()
