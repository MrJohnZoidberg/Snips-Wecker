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
from translation import Translation  # translation.py
import functools                     # functools.partial for threading.Timeout callback with parameter
import io                            # open the file for saving the alarms


class AlarmClock:
    def __init__(self, config):
        self.ringtone_wav = utils.edit_volume("alarm-sound.wav", utils.get_ringvol(config))
        self.ringing_timeout = utils.get_ringtmo(config)
        # self.dict_siteids -> { key=RoomName: value=siteId }
        self.dict_siteids = utils.get_dsiteid(config)
        # self.dict_rooms -> { key=siteId: value=RoomName }
        self.dict_rooms = {siteid: room for room, siteid in self.dict_siteids.iteritems()}
        self.default_room = utils.get_dfroom(config)
        self.saved_alarms_path = ".saved_alarms.json"
        self.remembered_slots = {}
        self.confirm_intents = {self.dict_siteids[room]: None for room in self.dict_siteids}
        # self.ringing_dict -> { key=siteId: value={ key='state' value=True/False; key='current_id' value=uuid} }
        self.ringing_dict = {self.dict_siteids[room]: {'state': False, 'current_id': None}
                             for room in self.dict_siteids}
        self.ringtone_status = utils.get_ringtonestat(config)
        self.siteids_session_not_ended = []  # list for func 'on_message_sessionstarted'
        self.alarms = self.read_alarms(utils.get_restorestat(config))
        self.clock_thread = threading.Thread(target=self.clock)
        self.clock_thread.start()
        # self.timeout_thr_dict -> { key=siteId: value=timeout_thread } (dict for threading-objects)
        self.timeout_thr_dict = {self.dict_siteids[room]: None for room in self.dict_siteids}
        self.missed_alarms = {}

        # Language
        self.language = "de-DE"
        self.translation = Translation(self.language)

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
                                3 - The slots are not properly filled
                                4 - Time of the alarm is in the past
                                5 - Difference of now-time and alarm-time too small
                    'fpart' - Part of the sentence which describes the future
                    'rpart' - Room name of the new alarm (context-dependent)
                    'hours' - Alarm time (hours)
                    'minutes' - Alarm time (minutes)
        """

        if len(self.dict_rooms) > 1:
            if 'room' in slots.keys():
                room_slot = slots['room']['value'].encode('utf8')
                if room_slot == self.translation.get("here"):
                    if siteid in self.dict_siteids.values():
                        alarm_site_id = siteid
                        room_part = self.translation.get("here")
                    else:
                        return "{} {}".format(self.translation.get("This room here hasn't been configured yet."),
                                              self.translation.get("Please see the instructions for this alarm clock "
                                                                   "app for how to add rooms."))
                else:
                    if room_slot in self.dict_siteids.keys():
                        alarm_site_id = self.dict_siteids[room_slot]
                        if siteid == self.dict_siteids[room_slot]:
                            room_part = self.translation.get("here")
                        else:
                            room_part = self.translation.get_prepos(room_slot) + " " + room_slot
                    else:
                        return "{} {}".format(self.translation.get("The room {room} has not been configured yet.",
                                                                   {'room': room_slot}),
                                              self.translation.get("Please see the instructions for this alarm clock "
                                                                   "app for how to add rooms."))
            else:
                alarm_site_id = self.dict_siteids[self.default_room]
                if siteid == self.dict_siteids[self.default_room]:
                    room_part = self.translation.get("here")
                else:
                    room_part = self.translation.get_prepos(self.default_room) + " " + self.default_room
        else:
            alarm_site_id = self.dict_siteids[self.default_room]
            room_part = ""
        # remove the timezone and some numbers from time string
        if slots['time']['kind'] == "InstantTime":
            alarm_time_str = ftime.alarm_time_str(slots['time']['value'])
        else:
            return self.translation.get("I'm afraid I didn't understand you.")
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if ftime.get_delta_obj(alarm_time).days < 0:  # if date is in the past
            return self.translation.get("This time is in the past. Please set another alarm.")
        elif ftime.get_delta_obj(alarm_time).seconds < 120:
            return self.translation.get("This alarm would ring now. Please set another alarm.")
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
            return self.translation.get("The alarm will ring {room_part} {future_part} at {h}:{min} .", {
                'future_part': self.get_future_part(alarm_time),
                'h': ftime.get_alarm_hour(alarm_time),
                'min': ftime.get_alarm_minute(alarm_time),
                'room_part': room_part})

    def get_alarms(self, slots, siteid):
        result = self.filter_alarms(self.alarms, slots, siteid)
        if result['rc'] == 1:
            return self.translation.get("This time is in the past. Please set another alarm.")
        elif result['rc'] == 2:
            return self.translation.get("I'm afraid I didn't understand you.")
        elif result['rc'] == 3:
            return "{} {}".format(self.translation.get("This room here hasn't been configured yet."),
                                  self.translation.get("Please see the instructions for this alarm clock "
                                                       "app for how to add rooms."))
        elif result['rc'] == 4:
            return "{} {}".format(self.translation.get("The room {room} has not been configured yet.",
                                                       {'room': result['room']}),
                                  self.translation.get("Please see the instructions for this alarm clock "
                                                       "app for how to add rooms."))

        alarm_count = result['alarm_count']
        if alarm_count == 0 or alarm_count == 1:
            if alarm_count == 0:
                count_part = self.translation.get("no alarm")
                end_part = "."
            else:
                count_part = self.translation.get("one alarm")
                end_part = " "
            response = self.translation.get("There is {room_part} {future_part} {time_part} {num_part}{end}",
                                            {'room_part': result['room_part'],
                                             'future_part': result['future_part'],
                                             'time_part': result['time_part'],
                                             'num_part': count_part,
                                             'end': end_part})
        else:
            count_part = self.translation.get("{num} alarms", {'num': alarm_count})
            end_part = ". "
            response = self.translation.get("There are {room_part} {future_part} {time_part} {num_part}{end}",
                                            {'room_part': result['room_part'],
                                             'future_part': result['future_part'],
                                             'time_part': result['time_part'],
                                             'num_part': count_part,
                                             'end': end_part})
        alarms = result['sorted_alarms']
        if alarm_count > 5:
            response += self.translation.get("The next five are: ")
            alarms = alarms[:5]

        """
        if len(result['alarms_sorted']) == 1:
            response += "{future_part} {room_part}".format(
                room_part=result['alarms_dict'][alarms[0]]['room_part'],
                future_part=result['alarms_dict'][alarms[0]]['future_part'])
        else:
        """

        for dtobj in alarms:
            # If room and/or time not said in speech command, the alarms were not filtered with that.
            # So these parts must be looked up for every datetime object.
            if not result['future_part']:
                future_part = self.get_future_part(dtobj, only_date=True)
            else:
                future_part = ""
            if result['time_part']:
                time_part = ""
            else:
                time_part = self.translation.get("at {h}:{min}", {'h': ftime.get_alarm_hour(dtobj),
                                                                  'min': ftime.get_alarm_minute(dtobj)})
            if not result['room_part']:
                room_part = self.get_roomstr(result['filtered_alarms'][dtobj], siteid)
            else:
                room_part = ""
            response += self.translation.get("{future_part} {time_part} {room_part}",
                                             {'room_part': room_part, 'time_part': time_part,
                                              'future_part': future_part})
            if dtobj != alarms[-1]:
                response += ", "
            else:
                response += "."
            if len(alarms) > 1 and dtobj == alarms[-2]:
                response += " {and_word} ".format(and_word=self.translation.get("and"))
        return response

    def get_missed(self, slots, siteid):
        result = self.filter_alarms(self.missed_alarms, slots, siteid, no_past=True)
        if result['rc'] == 2:
            return None, self.translation.get("I'm afraid I didn't understand you.")
        elif result['rc'] == 3:
            return None, "{} {}".format(self.translation.get("This room here hasn't been configured yet."),
                                        self.translation.get("Please see the instructions for this alarm clock "
                                                             "app for how to add rooms."))
        elif result['rc'] == 4:
            return None, "{} {}".format(self.translation.get("The room {room} has not been configured yet.",
                                                             {'room': result['room']}),
                                        self.translation.get("Please see the instructions for this alarm clock "
                                                             "app for how to add rooms."))
        # TODO

    def delete_alarms_try(self, slots, siteid):
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
        result = self.filter_alarms(self.alarms, slots, siteid)
        if result['rc'] == 1:
            return None, self.translation.get("This time is in the past. Please set another alarm.")
        elif result['rc'] == 2:
            return None, self.translation.get("I'm afraid I didn't understand you.")
        elif result['rc'] == 3:
            return None, "{} {}".format(self.translation.get("This room here hasn't been configured yet."),
                                        self.translation.get("Please see the instructions for this alarm clock "
                                                             "app for how to add rooms."))
        elif result['rc'] == 4:
            return None, "{} {}".format(self.translation.get("The room {room} has not been configured yet.",
                                                             {'room': result['room']}),
                                        self.translation.get("Please see the instructions for this alarm clock "
                                                             "app for how to add rooms."))
        if result['alarm_count'] >= 1:
            if result['alarm_count'] == 1:
                # TODO: Say future part and room part if single alarm delete
                # TODO: Say "der einzige" if this single alarm was the last one
                self.delete_alarms(result['filtered_alarms'])
                return None, self.translation.get("The alarm {future_part} {room_part} has been deleted.",
                                                  {'future_part': result['future_part'],
                                                   'room_part': result['room_part']})
            else:
                return result['filtered_alarms'],\
                       self.translation.get("There are {future_part} {room_part} {num} alarms. Are you sure?",
                                            {'future_part': result['future_part'],
                                             'room_part': result['room_part'],
                                             'num': result['alarm_count']})
        else:
            return None, self.translation.get("There is no alarm {room_part} {future_part}.",
                                              {'room_part': result['room_part'],
                                               'future_part': result['future_part']})

    def delete_alarms(self, alarms_delete):

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
        return self.translation.get("Done.")

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
                current_alarms = list(self.alarms[now_time])
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
                        self.ringing_dict[siteid]['state'] = True
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

        current_ringtone_id = str(uuid.uuid4())
        self.ringing_dict[siteid]['current_id'] = current_ringtone_id
        self.mqtt_client.publish('hermes/audioServer/{site_id}/playBytes/{ring_id}'.format(
            site_id=siteid, ring_id=current_ringtone_id), payload=self.ringtone_wav)

    def stop_ringing(self, siteid):

        """
        Sets self.ringing_dict[siteId] to False so on_message_playfinished won't start a new ring.
        :param siteid: The siteId of the user
        :return: Nothing
        """

        self.ringing_dict[siteid]['state'] = False
        self.ringing_dict[siteid]['current_id'] = None
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
        if self.ringing_dict[siteid]['state']:
            bytes_id = json.loads(msg.payload.decode("utf-8"))['id']
            if self.ringing_dict[siteid]['current_id'] == bytes_id:
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
        if self.ringing_dict[siteid]['state']:
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
        if self.ringing_dict[siteid]['state']:
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
                                     json.dumps({"text": self.translation.get("Alarm is now ended. It's {h}:{min} .", {
                                         'h': ftime.get_alarm_hour(now_time),
                                         'min': ftime.get_alarm_minute(now_time)}), "sessionId": data['sessionId']}))
            self.mqtt_client.message_callback_remove('hermes/dialogueManager/sessionStarted')
            self.siteids_session_not_ended.remove(data['siteId'])

    def on_message_setringtone(self, client, userdata, msg):

        """
        Called when 'external/alarmclock/setringtone' was received via MQTT. The message can include the
        binary data of the ringtone wav and whether the ringtone should be activated or deactivated.
        If it's deactivated only a MQTT message will be sent when ringing.
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

    def filter_alarms(self, alarms, slots, siteid, no_past=False):

        """Helper function which filters alarms with datetime and rooms"""

        future_part = ""
        time_part = ""
        room_part = ""
        # fill the list with all alarms and then filter it
        filtered_alarms = {dtobj: alarms[dtobj] for dtobj in alarms}
        dt_format = "%Y-%m-%d %H:%M"
        if 'time' in slots.keys():
            if slots['time']['kind'] == "InstantTime":
                alarm_time = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['value']), dt_format)
                future_part = self.get_future_part(alarm_time, only_date=True)
                if slots['time']['grain'] == "Hour" or slots['time']['grain'] == "Minute":
                    if not no_past and ftime.get_delta_obj(alarm_time, only_date=False).days < 0:
                        return {'rc': 1}
                    filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                       if dtobj == alarm_time}
                    time_part = self.translation.get("at {h}:{min}",
                                                     {'h': ftime.get_alarm_hour(alarm_time),
                                                      'min': ftime.get_alarm_minute(alarm_time)})
                else:
                    # TODO: Make more functional (with delta_object function)
                    now = datetime.datetime.now()
                    now_time_str = "{0}-{1}-{2}".format(now.year, now.month, now.day)
                    now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d")
                    delta_obj = (alarm_time.date() - now_time.date())
                    if delta_obj.days < 0:
                        return {'rc': 1}
                    filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                       if dtobj.date() == alarm_time.date()}
            elif slots['time']['kind'] == "TimeInterval":
                time_from = None
                time_to = None
                if slots['time']['from']:
                    time_from = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['from']), dt_format)
                if slots['time']['to']:
                    time_to = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['to']), dt_format)
                    if self.language == "de-DE":
                        time_to = ftime.nlu_time_bug_bypass(time_to)  # NLU bug (only German): hour or minute too much
                if not time_from and time_to:
                    filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms if dtobj <= time_to}
                elif not time_to and time_from:
                    filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms if time_from <= dtobj}
                else:
                    filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                       if time_from <= dtobj <= time_to}
                future_part = self.get_interval_part(time_from, time_to)
            else:
                return {'rc': 2}
        if 'room' in slots.keys():
            room_slot = slots['room']['value'].encode('utf8')
            if room_slot == self.translation.get("here"):
                if siteid in self.dict_siteids.values():
                    context_siteid = siteid
                else:
                    return {'rc': 3}
            else:
                if room_slot in self.dict_siteids.keys():
                    context_siteid = self.dict_siteids[room_slot]
                else:
                    return {'rc': 4, 'room': room_slot}
            filtered_alarms = {dtobj: [sid for sid in filtered_alarms[dtobj] if sid == context_siteid]
                               for dtobj in filtered_alarms}
            room_part = self.get_roomstr([context_siteid], siteid)
        filtered_alarms_sorted = [dtobj for dtobj in filtered_alarms if filtered_alarms[dtobj]]
        filtered_alarms_sorted.sort()
        alarm_count = len([sid for lst in filtered_alarms.itervalues() for sid in lst])
        return {
            'rc': 0,
            'filtered_alarms': filtered_alarms,
            'sorted_alarms': filtered_alarms_sorted,
            'alarm_count': alarm_count,
            'future_part': future_part,
            'time_part': time_part,
            'room_part': room_part
        }

    def get_roomstr(self, alarm_siteids, siteid):
        room_str = ""
        if len(self.dict_rooms) > 1:
            for iter_siteid in alarm_siteids:
                if iter_siteid == siteid:
                    room_str += self.translation.get("here")
                else:
                    current_room_prepos = self.translation.get_prepos(self.dict_rooms[iter_siteid])
                    room_str += "{prepos} {room}".format(prepos=current_room_prepos,
                                                         room=self.dict_rooms[iter_siteid])
                if len(alarm_siteids) > 1:
                    if iter_siteid != alarm_siteids[-1] and iter_siteid != alarm_siteids[-2]:
                        room_str += ", "
                    if iter_siteid == alarm_siteids[-2]:
                        room_str += " {and_word} ".format(and_word=self.translation.get("and"))
        return room_str

    def get_future_part(self, alarm_time, only_date=False):
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        alarm_weekday = self.translation.get(weekdays[alarm_time.weekday()])
        delta_days = ftime.get_delta_obj(alarm_time, only_date=True).days
        delta_hours = (alarm_time - ftime.get_now_time()).seconds // 3600
        if delta_hours <= 12 and not only_date:
            minutes_remain = ((alarm_time - ftime.get_now_time()).seconds % 3600) // 60
            if delta_hours == 1:  # for word fix in German
                hour_words = self.translation.get("one hour")
            else:
                hour_words = self.translation.get("{delta_hours} hours", {'delta_hours': delta_hours})
            if minutes_remain == 1:
                minute_words = self.translation.get("one minute")
            else:
                minute_words = self.translation.get("{delta_minutes} minutes", {'delta_minutes': minutes_remain})
            if delta_hours > 0 and minutes_remain == 0:
                return self.translation.get("in {hour_part}", {'hour_part': hour_words})
            elif delta_hours > 0 and minutes_remain > 0:
                return self.translation.get("in {hour_part} and {minute_part}", {'hour_part': hour_words,
                                                                                 'minute_part': minute_words})
            else:
                return "in {minute_part}".format(minute_part=minute_words)
        elif delta_days == 0:
            return self.translation.get("today")
        elif delta_days == 1:
            return self.translation.get("tomorrow")
        elif delta_days == 2:
            return self.translation.get("the day after tomorrow")
        elif 3 <= delta_days <= 6:
            return self.translation.get("on {weekday}", {'weekday': alarm_weekday})
        elif delta_days == 7:
            return self.translation.get("on {weekday} in exactly one week", {'weekday': alarm_weekday})
        else:
            return self.translation.get("in {delta_days} days, on {weekday}, the {day}.{month}.",
                                        {'delta_days': delta_days, 'weekday': alarm_weekday,
                                         'day': int(alarm_time.day), 'month': int(alarm_time.month)})

    def get_interval_part(self, from_time, to_time):
        if to_time:
            if to_time.date() != ftime.get_now_time().date():
                future_part_to = self.get_future_part(to_time, only_date=True)
            else:
                future_part_to = ""
            h_to = ftime.get_alarm_hour(to_time)
            min_to = ftime.get_alarm_minute(to_time)
            from_word = self.translation.get("from")
            to_part = self.translation.get("to {future_part_to} {h_to}:{min_to}", {'future_part_to': future_part_to,
                                                                                   'h_to': h_to, 'min_to': min_to})
        else:
            from_word = self.translation.get("as of")
            to_part = ""
        if from_time:
            if from_time.date() != ftime.get_now_time().date():
                future_part_from = self.get_future_part(from_time, only_date=True)
            else:
                future_part_from = ""
            h_from = ftime.get_alarm_hour(from_time)
            min_from = ftime.get_alarm_minute(from_time)
            from_part = self.translation.get("{from_word} {future_part_from} {h_from}:{min_from}",
                                             {'from_word': from_word, 'future_part_from': future_part_from,
                                              'h_from': h_from, 'min_from': min_from})
        else:
            from_part = ""
        return from_part + " " + to_part
