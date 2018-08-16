# -*- coding: utf-8 -*-
#                                    Explanations:
import datetime                      # date and time
import time                          # sleep in the clock thread
import threading                     # clock thread in background and alarm timeout
import paho.mqtt.client as mqtt      # sending mqtt messages
import json                          # payload in mqtt messages
import uuid                          # indentifier for wav-data send to audioserver
import utils                         # utils.py
import formattime as ftime           # ftime.py
import functools                     # functools.partial for threading.Timeout callback with parameter


class AlarmClock:
    def __init__(self, config):
        # Read config and correct values (in utils) if necessary
        self.ringing_timeout = utils.get_ringtmo(config)
        self.dict_siteid = utils.get_dsiteid(config)
        self.dict_prepositions = utils.get_dprepos(config)  # german prepositions for rooms
        self.default_room = utils.get_dfroom(config)
        self.ringtone_wav = utils.edit_volume("alarm-sound.wav", utils.get_ringvol(config))

        self.alarms = {}  # { key=datetime_obj: value=siteId_list }
        self.saved_alarms_path = ".saved_alarms.json"
        self.remembered_slots = {}
        self.wanted_intents = []
        # self.ringing_dict -> { key=siteId: value=True/False }
        self.ringing_dict = {self.dict_siteid[room]: False for room in self.dict_siteid}
        self.current_ring_ids = {self.dict_siteid[room]: None for room in self.dict_siteid}
        self.siteids_session_not_ended = []  # list for func 'on_message_sessionstarted'
        self.clock_thread = threading.Thread(target=self.clock)
        self.clock_thread.start()
        # self.timeout_thr_dict -> { key=siteId: value=timeout_thread } (dict for threading-objects)
        self.timeout_thr_dict = {self.dict_siteid[room]: None for room in self.dict_siteid}

        # Connect to MQTT broker
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.message_callback_add('hermes/hotword/#', self.on_message_hotword)
        self.mqtt_client.message_callback_add('external/alarmclock/stopringing', self.on_message_stopring)
        self.mqtt_client.connect(host="localhost", port=1883)
        self.mqtt_client.subscribe([('external/alarmclock/#', 0), ('hermes/dialogueManager/#', 0),
                                    ('hermes/hotword/#', 0), ('hermes/audioServer/#', 0)])
        self.mqtt_client.loop_start()

    def new_alarm(self, slots):
        room_part = ""
        if 'room' in slots.keys():
            # TODO: slots['room'].encode('utf8') only one time
            if slots['room'].encode('utf8') not in self.dict_siteid.keys():
                return "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von dieser " \
                       "Wecker-Äpp nach, wie man Räume hinzufügen kann.".format(room=slots['room'].encode('utf8'))
            alarm_site_id = self.dict_siteid[slots['room'].encode('utf8')]
            if len(self.dict_siteid) > 1:
                room_part = self.dict_prepositions[slots['room'].encode('utf8')] + " " + slots['room'].encode('utf8')
        else:
            alarm_site_id = self.dict_siteid[self.default_room]
            if len(self.dict_siteid) > 1:
                room_part = self.dict_prepositions[self.default_room] + " " + self.default_room
        # remove the timezone and some numbers from time string
        alarm_time_str = ftime.alarm_time_str(slots['time'])
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if ftime.get_delta_obj(alarm_time).days < 0:  # if date is in the past
            return "Diese Zeit liegt in der Vergangenheit. Wecker wurde nicht gestellt."
        elif ftime.get_delta_obj(alarm_time).seconds < 120:
            return "Dieser Alarm würde jetzt klingeln. Bitte wähle einen anderen Alarm."
        elif ftime.get_delta_obj(alarm_time).seconds >= 120:
            if alarm_time in self.alarms.keys():  # if list of siteIds already exists
                if alarm_site_id not in self.alarms[alarm_time]:
                    self.alarms[alarm_time].append(alarm_site_id)
            else:
                self.alarms[alarm_time] = [alarm_site_id]
            dt = datetime.datetime
            # alarm dictionary with datetime objects as strings { key=datetime_str: value=siteId_list }
            dic_al_str = {dt.strftime(dtobj, "%Y-%m-%d %H:%M"): self.alarms[dtobj] for dtobj in self.alarms}
            self.mqtt_client.publish('external/alarmclock/newalarm', json.dumps({'new': {'datetime': alarm_time_str,
                                                                                         'siteId': alarm_site_id},
                                                                                 'all': dic_al_str}))
            # TODO: names instead of numbers as placeholder
            return "Der Wecker wird {0} um {1} Uhr {2} {3} klingeln.".format(ftime.get_future_part(alarm_time),
                                                                             ftime.get_alarm_hour(alarm_time),
                                                                             ftime.get_alarm_minute(alarm_time),
                                                                             room_part)
        else:
            return "Der Alarm konnte nicht gestellt werden."

    def get_on_date(self, slots):
        wanted_date_str = slots['date'][:-16]  # remove the timezone and time from time string
        wanted_date = datetime.datetime.strptime(wanted_date_str, "%Y-%m-%d")
        if ftime.get_delta_obj(wanted_date, only_date=True).days < 0:
            return "Dieser Tag liegt in der Vergangenheit."
        alarms_on_date = []
        for alarm in self.alarms:
            if wanted_date.date() == alarm.date():
                alarms_on_date.append(alarm)
        if len(alarms_on_date) > 1:
            response = "{0} gibt es {1} Alarme. ".format(ftime.get_future_part(alarms_on_date[0], 1),
                                                         len(alarms_on_date))
            for alarm in alarms_on_date[:-1]:
                response = response + "einen um {0} Uhr {1}, ".format(ftime.get_alarm_hour(alarm),
                                                                      ftime.get_alarm_minute(alarm))
            response = response + "und einen um {0} Uhr {1} .".format(ftime.get_alarm_hour(alarms_on_date[-1]),
                                                                      ftime.get_alarm_minute(alarms_on_date[-1]))
        elif len(alarms_on_date) == 1:
            response = "{0} gibt es einen Alarm um {1} Uhr {2} .".format(
                ftime.get_future_part(alarms_on_date[0], 1),
                ftime.get_alarm_hour(alarms_on_date[0]),
                ftime.get_alarm_minute(alarms_on_date[0]))
        else:
            response = "{0} gibt es keinen Alarm.".format(ftime.get_future_part(wanted_date, only_date=True))
        return response

    def is_alarm(self, slots):
        asked_alarm_str = ftime.alarm_time_str(slots['time'])
        asked_alarm = datetime.datetime.strptime(asked_alarm_str, "%Y-%m-%d %H:%M")
        if asked_alarm in self.alarms.keys():
            return True, "Ja, {0} wird ein Alarm um {1} Uhr {2} " \
                         "klingeln.".format(ftime.get_future_part(asked_alarm, 1),
                                            ftime.get_alarm_hour(asked_alarm),
                                            ftime.get_alarm_minute(asked_alarm))
        else:
            self.remembered_slots = slots  # save slots for setting new alarm on confirmation
            return False, "Nein, zu dieser Zeit ist kein Alarm gestellt. Möchtest du " \
                          "{0} um {1} Uhr {2} einen Wecker stellen?".format(ftime.get_future_part(asked_alarm, 1),
                                                                            ftime.get_alarm_hour(asked_alarm),
                                                                            ftime.get_alarm_minute(asked_alarm))

    def delete_alarm(self, slots):
        alarm_str = ftime.alarm_time_str(slots['time'])
        alarm = datetime.datetime.strptime(alarm_str, "%Y-%m-%d %H:%M")
        if ftime.get_delta_obj(alarm).days < 0:
            return "Diese Zeit liegt in der Vergangenheit."
        if alarm in self.alarms.keys():
            del self.alarms[alarm]
            return "Der Alarm {0} um {1} Uhr {2} wurde entfernt.".format(ftime.get_future_part(alarm, 1),
                                                                         ftime.get_alarm_hour(alarm),
                                                                         ftime.get_alarm_minute(alarm))
        else:
            return "Dieser Alarm ist nicht vorhanden."

    def delete_date_try(self, slots):
        alarm_date_str = slots['date'][:-16]  # remove the timezone and time from time string
        alarm_date = datetime.datetime.strptime(alarm_date_str, "%Y-%m-%d")
        if ftime.get_delta_obj(alarm_date, only_date=True).days < 0:
            return False, "Dieser Tag liegt in der Vergangenheit."
        alarms_on_date = []
        for alarm in self.alarms:
            if alarm_date.date() == alarm.date():
                alarms_on_date.append(alarm)
        if len(alarms_on_date) > 1:
            self.remembered_slots = slots
            return True, "{0} gibt es {1} Alarme. Bist du dir sicher?".format(ftime.get_future_part(alarm_date, 1),
                                                                              len(alarms_on_date))
        elif len(alarms_on_date) == 1:
            self.remembered_slots = slots
            return True, "{0} gibt es einen Alarm um {1} Uhr {2} . Bist du dir sicher?".format(
                ftime.get_future_part(alarm_date, 1),
                ftime.get_alarm_hour(alarms_on_date[0]),
                ftime.get_alarm_minute(alarms_on_date[0]))
        else:
            return False, "{0} gibt es keinen Alarm.".format(ftime.get_future_part(alarm_date, only_date=True))

    def delete_date(self, slots):
        if slots['answer'] == "yes":
            # date was saved above in global self.slots
            alarm_date_str = self.remembered_slots['date'][:-16]  # remove the timezone and time from date string
            alarm_date = datetime.datetime.strptime(alarm_date_str, "%Y-%m-%d")
            for alarm, details in self.alarms:
                if alarm_date.date() == alarm.date():
                    del self.alarms[alarm]
            return "Alle Alarme {0} wurden entfernt.".format(ftime.get_future_part(alarm_date, 1))
        else:
            return "Vorgang wurde abgebrochen."

    def delete_all_try(self):
        if len(self.alarms) == 1:
            return True, "Es ist ein Alarm aktiv. Bist du dir sicher?"
        elif len(self.alarms) > 1:
            return True, "In der nächsten Zeit gibt es {num} Alarme. Bist du dir sicher?".format(num=len(self.alarms))
        else:
            return False, "Es sind keine Alarme gestellt."

    def delete_all(self, slots):
        if slots['answer'] == "yes":
            self.alarms = {}
            utils.save_alarms(self.alarms, self.saved_alarms_path)
            return "Es wurden alle Alarme entfernt."
        else:
            return "Vorgang wurde abgebrochen."

    def get_all(self):
        if len(self.alarms) == 0:
            response = "Es gibt keine gestellten Alarme."
        elif len(self.alarms) == 1:
            single_alarm = ""
            for alarm, details in self.alarms:
                single_alarm = alarm
            response = "Es gibt {0} einen Alarm um {1} Uhr {2} .".format(
                ftime.get_future_part(single_alarm, 1),
                ftime.get_alarm_hour(single_alarm),
                ftime.get_alarm_minute(single_alarm))
        elif 2 <= len(self.alarms) <= 5:
            response = "Es gibt {0} Alarme in der nächsten Zeit. ".format(len(self.alarms))
            alarms_list = []
            for alarm, details in self.alarms:
                alarms_list.append(alarm)
            for alarm in alarms_list[:-1]:
                response = response + "einen {0} um {1} Uhr {2}, ".format(ftime.get_future_part(alarm, 1),
                                                                          ftime.get_alarm_hour(alarm),
                                                                          ftime.get_alarm_minute(alarm))
            response = response + "und einen {0} um {1} Uhr {2} .".format(
                ftime.get_future_part(alarms_list[-1], 1),
                ftime.get_alarm_hour(alarms_list[-1]),
                ftime.get_alarm_minute(alarms_list[-1]))
        else:
            response = "Die nächsten sechs Alarme sind "
            alarms_list = []
            for alarm, details in self.alarms:
                alarms_list.append(alarm)
            for alarm in alarms_list[:6]:
                response = response + "einmal {0} um {1} Uhr {2}, ".format(ftime.get_future_part(alarm, 1),
                                                                           ftime.get_alarm_hour(alarm),
                                                                           ftime.get_alarm_minute(alarm))
            response = response + "und {0} um {1} Uhr {2} .".format(ftime.get_future_part(alarms_list[-1], 1),
                                                                    ftime.get_alarm_hour(alarms_list[-1]),
                                                                    ftime.get_alarm_minute(alarms_list[-1]))
        return response

    def clock(self):

        """Checks in a loop if the current time and date matches with one of the alarm dictionary"""

        while True:
            now_time = ftime.get_now_time()
            if now_time in self.alarms.keys():
                # make copy of list for the for-loop, because next step is deleting the alarm
                current_alarms = self.alarms[now_time]
                for siteid in current_alarms:
                    if len(self.alarms[now_time]) == 1:
                        del self.alarms[now_time]
                    else:
                        self.alarms[now_time].remove(siteid)
                    self.mqtt_client.message_callback_add('hermes/audioServer/{site_id}/playFinished'.format(
                        site_id=siteid), self.on_message_playfinished)
                    self.ring(siteid)
                    self.ringing_dict[siteid] = True
                    self.mqtt_client.publish('external/alarmlock/ringing', json.dumps({'siteId': siteid}))
                    timeout_thread = threading.Timer(self.ringing_timeout, functools.partial(self.stop_ringing, siteid))
                    self.timeout_thr_dict[siteid] = timeout_thread
                    timeout_thread.start()
            time.sleep(3)

    def ring(self, siteid):

        """Publishes the ringtone wav over MQTT to the soundserver and generates a random
        UUID so that self.on_message_playfinished can identify it to start a new ring."""

        self.current_ring_ids[siteid] = uuid.uuid4()
        self.mqtt_client.publish('hermes/audioServer/{site_id}/playBytes/{ring_id}'.format(
            site_id=siteid, ring_id=self.current_ring_ids[siteid]), payload=self.ringtone_wav)

    def stop_ringing(self, siteid):

        """Sets self.ringing_dict[siteId] to False so on_message_playfinished won't start a new ring."""

        self.ringing_dict[siteid] = False
        self.timeout_thr_dict[siteid].cancel()  # cancel timeout thread from siteId
        self.timeout_thr_dict[siteid] = None
        self.mqtt_client.message_callback_remove('hermes/audioServer/{site_id}/playFinished'.format(site_id=siteid))

    def on_message_playfinished(self, client, userdata, msg):

        """Called when ringtone was played on specific site. If self.ringing_dict[siteId] is
        True and the ID matches the one sent out, the ringtone is played again."""
        data = json.loads(msg.payload.decode("utf-8"))
        print("Play finished................................", data['siteId'], self.ringing_dict)
        if self.ringing_dict[data['siteId']]:
            # TODO: Find out whether this identification is necessary (check function description when finished):
            if uuid.UUID(data['id']) == self.current_ring_ids[data['siteId']]:
                self.ring(data['siteId'])

    def on_message_hotword(self, client, userdata, msg):

        """Called when hotword is recognized while alarm is ringing. If siteId
        matches the one of the current ringing alarm, it is stopped."""

        data = json.loads(msg.payload.decode("utf-8"))
        if self.ringing_dict[data['siteId']]:
            self.stop_ringing(data['siteId'])
            self.siteids_session_not_ended.append(data['siteId'])
            self.mqtt_client.message_callback_add('hermes/dialogueManager/sessionStarted',
                                                  self.on_message_sessionstarted)

    def on_message_stopring(self, client, userdata, msg):

        """Called when message 'external/alarmclock/stopringing' is received via MQTT."""

        data = json.loads(msg.payload.decode("utf-8"))
        if self.ringing_dict[data['siteId']]:
            self.stop_ringing(data['siteId'])

    def on_message_sessionstarted(self, client, userdata, msg):

        """Called when Snips started a new session. Publishes a message to end this
        immediately and Snips will notify the user that the alarm has ended."""

        data = json.loads(msg.payload.decode("utf-8"))
        if data['siteId'] in self.siteids_session_not_ended:
            self.mqtt_client.publish('hermes/dialogueManager/endSession',
                                     json.dumps({"text": "Alarm beendet", "sessionId": data['sessionId']}))
            self.mqtt_client.message_callback_remove('hermes/dialogueManager/sessionStarted')
            self.siteids_session_not_ended.remove(data['siteId'])
