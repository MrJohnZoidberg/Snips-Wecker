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
import io                            # open the file for saving the alarms


class AlarmClock:
    def __init__(self, ringtone_wav=None, ringing_timeout=None, dict_siteid=None, default_room=None,
                 restore_alarms=True, ringtone_status=True):
        self.ringtone_wav = ringtone_wav
        self.ringing_timeout = ringing_timeout
        # self.dict_siteids -> { key=RoomName: value=siteId }
        self.dict_siteids = dict_siteid
        # self.dict_rooms -> { key=siteId: value=RoomName }
        self.dict_rooms = {siteid: room for room, siteid in self.dict_siteids.iteritems()}
        self.default_room = default_room
        self.saved_alarms_path = ".saved_alarms.json"
        self.remembered_slots = {}
        self.confirm_intents = {self.dict_siteids[room]: None for room in self.dict_siteids}
        # self.ringing_dict -> { key=siteId: value=True/False }
        self.ringing_dict = {self.dict_siteids[room]: False for room in self.dict_siteids}
        self.ringtone_status = ringtone_status
        self.siteids_session_not_ended = []  # list for func 'on_message_sessionstarted'
        self.alarms = self.read_alarms(restore_alarms)
        self.clock_thread = threading.Thread(target=self.clock)
        self.clock_thread.start()
        # self.timeout_thr_dict -> { key=siteId: value=timeout_thread } (dict for threading-objects)
        self.timeout_thr_dict = {self.dict_siteids[room]: None for room in self.dict_siteids}

        # Connect to MQTT broker
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.message_callback_add('hermes/hotword/#', self.on_message_hotword)
        # TODO: Publish other messages over mqtt
        self.mqtt_client.message_callback_add('external/alarmclock/stopRinging', self.on_message_stopringing)
        self.mqtt_client.message_callback_add('external/alarmclock/setRingtone', self.on_message_setringtone)
        self.mqtt_client.connect(host="localhost", port=1883)
        self.mqtt_client.subscribe([('external/alarmclock/#', 0), ('hermes/dialogueManager/#', 0),
                                    ('hermes/hotword/#', 0), ('hermes/audioServer/#', 0)])
        self.mqtt_client.loop_start()

    def new_alarm(self, slots, siteid):

        """
        Callend when creating a new alarm. Logic: see ../resources/Snips-Alarmclock-newAlarm.png
        :param slots: The slots of the intent from the NLU
        :param siteid: The siteId of the device where the user has spoken
        :return: Dictionary with some keys:
                    'rc' - Return code: Numbers representing normal or error message.
                                0 - Everything good, alarm was created (other keys below are available)
                                1 - This room is not configured (if slot 'room' is "hier")
                                2 - Room 'room' is not configured (if slot 'room' is not "hier")
                                3 - Time of the alarm is in the past
                                4 - Difference of now-time and alarm-time too small
                    'fpart' - Part of the sentence which describes the future
                    'rpart' - Room name of the new alarm (context-dependent)
                    'hours' - Alarm time (hours)
                    'minutes' - Alarm time (minutes)
        """

        if len(self.dict_rooms) > 1:
            if 'room' in slots.keys():
                room_slot = slots['room'].encode('utf8')
                if room_slot == "hier":
                    if siteid in self.dict_siteids.values():
                        alarm_site_id = siteid
                        room_part = "hier"
                    else:
                        return {'rc': 1}
                else:
                    if room_slot in self.dict_siteids.keys():
                        alarm_site_id = self.dict_siteids[room_slot]
                        if siteid == self.dict_siteids[room_slot]:
                            room_part = "hier"
                        else:
                            room_part = utils.get_prepos(room_slot) + " " + room_slot
                    else:
                        return {'rc': 2, 'room': room_slot}
            else:
                alarm_site_id = self.dict_siteids[self.default_room]
                if siteid == self.dict_siteids[self.default_room]:
                    room_part = "hier"
                else:
                    room_part = utils.get_prepos(self.default_room) + " " + self.default_room
        else:
            alarm_site_id = self.dict_siteids[self.default_room]
            room_part = ""
        # remove the timezone and some numbers from time string
        alarm_time_str = ftime.alarm_time_str(slots['time'])
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if ftime.get_delta_obj(alarm_time).days < 0:  # if date is in the past
            return {'rc': 3}
        elif ftime.get_delta_obj(alarm_time).seconds < 120:
            return {'rc': 4}
        else:
            if alarm_time in self.alarms.keys():  # if list of siteIds already exists
                if alarm_site_id not in self.alarms[alarm_time]:
                    self.alarms[alarm_time].append(alarm_site_id)
            else:
                self.alarms[alarm_time] = [alarm_site_id]
            self.save_alarms()
            dt = datetime.datetime
            # alarm dictionary with datetime objects as strings { key=datetime_str: value=siteId_list }
            dic_al_str = {dt.strftime(dtobj, "%Y-%m-%d %H:%M"): self.alarms[dtobj] for dtobj in self.alarms}
            self.mqtt_client.publish('external/alarmclock/newalarm', json.dumps({'new': (alarm_time_str, alarm_site_id),
                                                                                 'all': dic_al_str}))
            return {'rc': 0, 'fpart': ftime.get_future_part(alarm_time), 'hours': ftime.get_alarm_hour(alarm_time),
                    'minutes': ftime.get_alarm_minute(alarm_time), 'rpart': room_part}

    def get_alarms(self, slots, siteid):
        future_part = ""
        room_part = ""
        # fill the list with all alarms and then filter it
        filtered_alarms = {dtobj: self.alarms[dtobj] for dtobj in self.alarms}
        if 'date' in slots.keys():
            # TODO: Until (Alle alarme vor neunzehn uhr)
            alarm_date = datetime.datetime.strptime(slots['date'][:-16], "%Y-%m-%d")
            if ftime.get_delta_obj(alarm_date, only_date=True).days >= 0:
                filtered_alarms = {dtobj: self.alarms[dtobj] for dtobj in filtered_alarms
                                   if dtobj.date() == alarm_date.date()}
                future_part = ftime.get_future_part(alarm_date, only_date=True)
            else:
                return {'rc': 3}
        if 'room' in slots.keys():
            room_slot = slots['room'].encode('utf8')
            if room_slot == "hier":
                if siteid in self.dict_siteids.values():
                    context_siteid = siteid
                else:
                    return {'rc': 1}
            else:
                if room_slot in self.dict_siteids.keys():
                    context_siteid = self.dict_siteids[room_slot]
                else:
                    return {'rc': 2, 'room': room_slot}
            filtered_alarms = {dtobj: [sid for sid in filtered_alarms[dtobj] if sid == context_siteid]
                               for dtobj in filtered_alarms}
            room_part = utils.get_roomstr([context_siteid], self.dict_rooms, siteid)
        filtered_alarms = {dtobj: filtered_alarms[dtobj] for dtobj in filtered_alarms}
        filtered_alarms_sorted = [dtobj for dtobj in filtered_alarms if filtered_alarms[dtobj]]
        filtered_alarms_sorted.sort()
        filtered_alarms_dict = {}
        for dtobj in filtered_alarms:
            filtered_alarms_dict[dtobj] = {}
            filtered_alarms_dict[dtobj]['hours'] = ftime.get_alarm_hour(dtobj)
            filtered_alarms_dict[dtobj]['minutes'] = ftime.get_alarm_minute(dtobj)
            if not future_part:
                filtered_alarms_dict[dtobj]['future_part'] = ftime.get_future_part(dtobj, only_date=True)
            else:
                filtered_alarms_dict[dtobj]['future_part'] = ""
            if not room_part:
                filtered_alarms_dict[dtobj]['room_part'] = utils.get_roomstr(filtered_alarms[dtobj], self.dict_rooms,
                                                                             siteid)
            else:
                filtered_alarms_dict[dtobj]['room_part'] = ""
        alarm_count = len([sid for lst in filtered_alarms.itervalues() for sid in lst])
        return {'rc': 0, 'alarms_sorted': filtered_alarms_sorted, 'room_part': room_part, 'future_part': future_part,
                'alarm_count': alarm_count, 'alarms_dict': filtered_alarms_dict}

    def is_alarm(self, slots, siteid):
        asked_alarm_str = ftime.alarm_time_str(slots['time'])
        asked_alarm = datetime.datetime.strptime(asked_alarm_str, "%Y-%m-%d %H:%M")
        room_part = ""
        if asked_alarm in self.alarms.keys():
            isalarm = True
        else:
            isalarm = False
        if len(self.dict_rooms) > 1:
            if 'room' in slots.keys():
                room_slot = slots['room'].encode('utf8')
                if room_slot == "hier":
                    if siteid in self.dict_siteids.values():
                        room_part = "hier"
                    else:
                        return {'rc': 1}
                else:
                    if room_slot in self.dict_siteids.keys():
                        if siteid == self.dict_siteids[room_slot]:
                            room_part = "hier"
                        else:
                            room_part = utils.get_prepos(room_slot) + " " + room_slot
                    else:
                        return {'rc': 2, 'room': room_slot}
            elif isalarm:
                    room_part = utils.get_roomstr(self.alarms[asked_alarm], self.dict_rooms, siteid)
        if ftime.get_delta_obj(asked_alarm).days < 0:  # if date is in the past
            return {'rc': 3}
        else:
            self.remembered_slots[siteid] = slots
            return {'rc': 0, 'is_alarm': isalarm, 'future_part': ftime.get_future_part(asked_alarm, only_date=True),
                    'hours': ftime.get_alarm_hour(asked_alarm), 'minutes': ftime.get_alarm_minute(asked_alarm),
                    'room_part': room_part}

    def delete_single(self, slots):
        # TODO
        alarm_str = ftime.alarm_time_str(slots['time'])
        alarm = datetime.datetime.strptime(alarm_str, "%Y-%m-%d %H:%M")
        room_slot = slots['room'].encode('utf8')
        if ftime.get_delta_obj(alarm).days < 0:
            return "Diese Zeit liegt in der Vergangenheit."
        if alarm in self.alarms.keys():
            del self.alarms[alarm]
            self.save_alarms()
            return "Der Alarm {0} um {1} Uhr {2} wurde entfernt.".format(ftime.get_future_part(alarm, 1),
                                                                         ftime.get_alarm_hour(alarm),
                                                                         ftime.get_alarm_minute(alarm))
        else:
            return "Dieser Alarm ist nicht vorhanden."

    def delete_multi_try(self, slots, siteid):

        """
        Called when the user want to delete multiple alarms. If user said room and/or date the alarms with these
        properties will be deleted. Otherwise all alarms will be deleted.
        :param slots: The slots of the intent from Snips
        :param siteid: The siteId where the user triggered the intent
        :return: Dictionary with some keys:
            'rc' - Return code: Numbers representing normal or error message.
                        0 - Everything good (other keys below are available)
                        1 - This room is not configured (if slot 'room' is "hier")
                        2 - Room 'room' is not configured (if slot 'room' is not "hier")
                        3 - Date is in the past
            'matching_alarms' - List with datetime objects which will be deleted on confirmation
            'future_part' - Part of the sentence which describes the future
            'room_part' - Room name of the alarms (context-dependent)
            'alarm_count' - Number of matching alarms (if alarms are ringing in two rooms at
                            one time, this means two alarms)
        """

        future_part = ""
        room_part = ""
        # fill the list with all alarms and then filter it
        filtered_alarms = {dtobj: self.alarms[dtobj] for dtobj in self.alarms}
        if 'date' in slots.keys():
            # TODO: Until (Alle alarme vor neunzehn uhr)
            alarm_date = datetime.datetime.strptime(slots['date'][:-16], "%Y-%m-%d")
            if ftime.get_delta_obj(alarm_date, only_date=True).days >= 0:
                filtered_alarms = {dtobj: self.alarms[dtobj] for dtobj in filtered_alarms
                                   if dtobj.date() == alarm_date.date()}
                future_part = ftime.get_future_part(alarm_date, only_date=True)
            else:
                return {'rc': 3}
        if 'room' in slots.keys():
            room_slot = slots['room'].encode('utf8')
            if room_slot == "hier":
                if siteid in self.dict_siteids.values():
                    context_siteid = siteid
                else:
                    return {'rc': 1}
            else:
                if room_slot in self.dict_siteids.keys():
                    context_siteid = self.dict_siteids[room_slot]
                else:
                    return {'rc': 2, 'room': room_slot}
            filtered_alarms = {dtobj: [sid for sid in filtered_alarms[dtobj] if sid == context_siteid]
                               for dtobj in filtered_alarms}
            room_part = utils.get_roomstr([context_siteid], self.dict_rooms, siteid)
        alarm_count = len([sid for lst in filtered_alarms.itervalues() for sid in lst])
        return {'rc': 0, 'matching_alarms': filtered_alarms, 'room_part': room_part, 'future_part': future_part,
                'alarm_count': alarm_count}

    def delete_multi(self, alarms_delete):

        """
        Removes all alarms in the dictionary "alarms_delete". First it deletes siteids from self.alarms if they
        are in filtered_alarms and second it removes datetime (dt) objects with empty siteid list.
        :param alarms_delete: Dictionary with the same structure as the self.alarms dict, but it only includes
                              datetime objects together with a siteId list which should be deleted.
                              { key=dtobject: value=listWithSiteIds }
        :return: Dictionary: 'rc' - Return code (0 = no error)
        """

        self.alarms = {dtobj: [sid for sid in self.alarms[dtobj]
                               if sid not in [x for lst in alarms_delete.itervalues() for x in lst]
                               or dtobj not in alarms_delete.keys()] for dtobj in self.alarms}
        self.alarms = {dtobj: self.alarms[dtobj] for dtobj in self.alarms if self.alarms[dtobj]}
        self.save_alarms()
        return {'rc': 0}

    def save_alarms(self, path=None):
        if not path:
            path = self.saved_alarms_path
        dic_al_str = {datetime.datetime.strftime(dtobj, "%Y-%m-%d %H:%M"): self.alarms[dtobj] for dtobj in self.alarms}
        with io.open(path, "w") as f:
            f.write(unicode(json.dumps(dic_al_str)))

    def read_alarms(self, restore_alarms):
        if restore_alarms:
            with io.open(self.saved_alarms_path, "r") as f:
                try:
                    dic_al_str = json.load(f)
                except ValueError:
                    dic_al_str = {}
        else:
            dic_al_str = {}  # { key=datetime_obj: value=siteId_list }
        alarms = {datetime.datetime.strptime(dtstr, "%Y-%m-%d %H:%M"): dic_al_str[dtstr] for dtstr in dic_al_str}
        return alarms

    def clock(self):

        """
        Checks in a loop if the current time and date matches with one of the alarm dictionary.
        :return: Nothing
        """

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
                    self.save_alarms()
                    room = self.dict_rooms[siteid]
                    self.mqtt_client.publish('external/alarmclock/ringing', json.dumps({'siteId': siteid,
                                                                                        'room': room}))
                    if self.ringtone_status:
                        self.mqtt_client.message_callback_add('hermes/audioServer/{site_id}/playFinished'.format(
                            site_id=siteid), self.on_message_playfinished)
                        self.ring(siteid)
                        self.ringing_dict[siteid] = True
                        timeout_thread = threading.Timer(self.ringing_timeout,
                                                         functools.partial(self.stop_ringing, siteid))
                        self.timeout_thr_dict[siteid] = timeout_thread
                        timeout_thread.start()
            time.sleep(3)

    def ring(self, siteid):

        """
        Publishes the ringtone wav over MQTT to the soundserver and generates a random UUID for it.
        :param siteid: The siteId of the user
        :return: Nothing
        """

        self.mqtt_client.publish('hermes/audioServer/{site_id}/playBytes/{ring_id}'.format(
            site_id=siteid, ring_id=uuid.uuid4()), payload=self.ringtone_wav)

    def stop_ringing(self, siteid):

        """
        Sets self.ringing_dict[siteId] to False so on_message_playfinished won't start a new ring.
        :param siteid: The siteId of the user
        :return: Nothing
        """

        self.ringing_dict[siteid] = False
        self.timeout_thr_dict[siteid].cancel()  # cancel timeout thread from siteId
        self.timeout_thr_dict[siteid] = None
        self.mqtt_client.message_callback_remove('hermes/audioServer/{site_id}/playFinished'.format(site_id=siteid))

    def on_message_playfinished(self, client, userdata, msg):

        """
        Called when ringtone was played on specific site. If self.ringing_dict[siteId] is True, the
        ringtone is played again.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        siteid = json.loads(msg.payload.decode("utf-8"))['siteId']
        if siteid in self.ringing_dict.keys():
            self.ring(siteid)

    def on_message_hotword(self, client, userdata, msg):

        """
        Called when hotword is recognized while alarm is ringing. If siteId matches the one of the
        current ringing alarm, it is stopped.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        siteid = json.loads(msg.payload.decode("utf-8"))['siteId']
        if self.ringing_dict[siteid]:
            self.stop_ringing(siteid)
            self.siteids_session_not_ended.append(siteid)
            self.mqtt_client.message_callback_add('hermes/dialogueManager/sessionStarted',
                                                  self.on_message_sessionstarted)

    def on_message_stopringing(self, client, userdata, msg):

        """
        Called when message 'external/alarmclock/stopRinging' was received via MQTT.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        siteid = json.loads(msg.payload.decode("utf-8"))['siteId']
        if self.ringing_dict[siteid]:
            self.stop_ringing(siteid)

    def on_message_sessionstarted(self, client, userdata, msg):

        """
        Called when Snips started a new session. Publishes a message to end this immediately and Snips
        will notify the user that the alarm has ended.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        data = json.loads(msg.payload.decode("utf-8"))
        if data['siteId'] in self.siteids_session_not_ended:
            now_time = datetime.datetime.now()
            self.mqtt_client.publish('hermes/dialogueManager/endSession',
                                     json.dumps({"text": "Alarm beendet. Es ist jetzt {h} Uhr {min}".format(
                                         h=now_time.hour, min=now_time.minute), "sessionId": data['sessionId']}))
            self.mqtt_client.message_callback_remove('hermes/dialogueManager/sessionStarted')
            self.siteids_session_not_ended.remove(data['siteId'])

    def on_message_setringtone(self, client, userdata, msg):

        """
        Called when 'external/alarmclock/setringtone' was received via MQTT. The message can include the
        binary data of the ringtone wav and whether the ringtone should be activated or deactivated.
        If it's deactivated only a MQTT message will be sent.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        data = json.loads(msg.payload.decode("utf-8"))
        if 'status' in data.keys():
            if data['status'].lower() == "on":
                self.ringtone_status = True
            elif data['status'].lower() == "off":
                self.ringtone_status = False
        if 'ringtoneBytes' in data.keys():
            self.ringtone_wav = data['ringtoneBytes']
