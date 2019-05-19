# -*- coding: utf-8 -*-
#                                    Explanations:
import datetime                      # date and time
import paho.mqtt.client as mqtt      # sending mqtt messages
import json                          # payload in mqtt messages
from . import utils                         # utils.py
from . import formattime as ftime           # ftime.py
from . alarm import Alarm, AlarmControl
from . translation import Translation  # translation.py


class AlarmClock:
    def __init__(self):
        self.config = utils.get_config("config.ini", "config.ini.default")
        # self.dict_siteids -> { key=RoomName: value=siteId }
        self.dict_siteids = self.config['dict_siteids']
        self.default_room = self.config['default_room']
        self.remembered_slots = {}
        self.temp_memory = {self.dict_siteids[room]: None for room in self.dict_siteids}
        # Language
        self.language = "de-DE"
        self.translation = Translation(self.language)
        # Connect to MQTT broker
        self.mqtt_client = mqtt.Client()
        # TODO: Publish other messages over mqtt
        self.mqtt_client.connect(host="localhost", port=1883)
        self.mqtt_client.subscribe([('external/alarmclock/#', 0), ('hermes/dialogueManager/#', 0),
                                    ('hermes/hotword/#', 0), ('hermes/audioServer/#', 0)])
        # Create alarmcontrol instance
        self.alarmctl = AlarmControl(self.config, self.language, self.mqtt_client, self.temp_memory)
        # Start MQTT-Loop
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

        if not slots:
            return self.error_understanding()

        if len(self.alarmctl.sites_dict) > 1:
            if 'room' in slots.keys():
                room_slot = slots['room']
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
                    room_part = "{} {}".format(self.translation.get_prepos(self.default_room),
                                               self.default_room)
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
            return "{} {}".format(self.translation.get("This time is in the past."),
                                  self.translation.get("Please set another alarm."))
        elif ftime.get_delta_obj(alarm_time).seconds < 120:
            return "{} {}".format(self.translation.get("This alarm would ring now."),
                                  self.translation.get("Please set another alarm."))
        else:
            alarm = Alarm(alarm_time, self.alarmctl.sites_dict[alarm_site_id], repetition=None)
            self.alarmctl.add(alarm)
            # alarm dictionary with datetime objects as strings { key=datetime_str: value=siteId_list }
            self.mqtt_client.publish('external/alarmclock/newalarm',
                                     json.dumps({'new': alarm.get_data_dict(),
                                                 'all': self.alarmctl.get_unpacked_objects_list()}))
            response = self.translation.get("The alarm will ring {room_part} {future_part} at {h}:{min} .", {
                'future_part': self.get_time_description(alarm_time),
                'h': ftime.get_alarm_hour(alarm_time),
                'min': ftime.get_alarm_minute(alarm_time),
                'room_part': room_part})
            return self.del_multi_spaces(response)

    def get_alarms(self, slots, siteid):
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_alarms(), slots, siteid)

        if rc > 0:
            return self.error_sentence(rc, words_dict)

        alarm_count = len(filtered_alarms)
        if alarm_count <= 1:
            if alarm_count == 0:
                count_part = self.translation.get("no alarm")
                end_part = "."
            else:
                count_part = self.translation.get("one alarm")
                end_part = " "
            response = self.translation.get("There is {room_part} {future_part} {time_part} {num_part}{end}",
                                            {'room_part': words_dict['room_part'],
                                             'future_part': words_dict['future_part'],
                                             'time_part': words_dict['time_part'],
                                             'num_part': count_part, 'end': end_part})
        else:
            count_part = self.translation.get("{num} alarms", {'num': alarm_count})
            end_part = ". "
            response = self.translation.get("There are {room_part} {future_part} {time_part} {num_part}{end}",
                                            {'room_part': words_dict['room_part'],
                                             'future_part': words_dict['future_part'],
                                             'time_part': words_dict['time_part'],
                                             'num_part': count_part, 'end': end_part})
        if alarm_count > 5:
            response += self.translation.get("The next five are: ")
            filtered_alarms = filtered_alarms[:5]

        response = self.add_alarms_part(response, siteid, filtered_alarms, words_dict, alarm_count)
        return self.del_multi_spaces(response)

    def get_next_alarm(self, slots, siteid):
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_alarms(), slots, siteid)

        if rc > 0:
            return self.error_sentence(rc, words_dict)

        if filtered_alarms:
            next_alarm = filtered_alarms[0]

            if words_dict['room_part']:
                room_part = ""
            else:
                room_part = self.get_roomstr([next_alarm.site.siteid], siteid)
            response = self.translation.get("The next alarm {room_slot} starts {future_part} at {h}:{min} {room_part}.",
                                            {'room_slot': words_dict['room_part'],
                                             'future_part': self.get_time_description(next_alarm.datetime),
                                             'h': ftime.get_alarm_hour(next_alarm.datetime),
                                             'min': ftime.get_alarm_minute(next_alarm.datetime),
                                             'room_part': room_part})
        else:
            response = self.translation.get("There is {room_part} {future_part} {time_part} {num_part}{end}",
                                            {'room_part': words_dict['room_part'],
                                             'future_part': words_dict['future_part'],
                                             'time_part': words_dict['time_part'],
                                             'num_part': self.translation.get("no alarm"),
                                             'end': "."})
        return self.del_multi_spaces(response)

    def get_missed_alarms(self, slots, siteid):
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_missed_alarms(),
                                                             slots, siteid, timeslot_with_past=True)
        if rc > 0:
            return self.error_sentence(rc, words_dict)
        filtered_alarms.sort(reverse=True)  # sort from old to new (say oldest alarms first)

        alarm_count = len(filtered_alarms)
        if alarm_count <= 1:
            if alarm_count == 0:
                count_part = self.translation.get("no alarm")
                end_part = "."
            else:
                count_part = self.translation.get("one alarm")
                end_part = " "
        else:
            count_part = self.translation.get("{num} alarms", {'num': alarm_count})
            end_part = ". "
        response = self.translation.get("You missed {room_part} {future_part} {time_part} {num_part}{end}",
                                        {'room_part': words_dict['room_part'],
                                         'future_part': words_dict['future_part'],
                                         'time_part': words_dict['time_part'],
                                         'num_part': count_part, 'end': end_part})
        response = self.add_alarms_part(response, siteid, filtered_alarms, words_dict, alarm_count)
        self.alarmctl.delete_multi(filtered_alarms)  # Like a mailbox: Say missed messages and delete them after that.
        return self.del_multi_spaces(response)

    def add_alarms_part(self, response, siteid, filtered_alarms, words_dict, alarm_count):
        for alarm in filtered_alarms:
            dtobj = alarm.datetime
            # If room and/or time not said in speech command, the alarms were not filtered with that.
            # So these parts must be looked up for every datetime object.
            if not words_dict['future_part']:
                future_part = self.get_time_description(dtobj, only_days=True)
            else:
                future_part = ""
            if words_dict['time_part']:
                time_part = ""
            else:
                time_part = self.translation.get("at {h}:{min}", {'h': ftime.get_alarm_hour(dtobj),
                                                                  'min': ftime.get_alarm_minute(dtobj)})
            if not words_dict['room_part']:
                room_part = self.get_roomstr([alarm.site.siteid for alarm in self.alarmctl.get_alarms(dtobj)], siteid)
            else:
                room_part = ""
            response += self.translation.get("{future_part} {time_part} {room_part}",
                                             {'room_part': room_part, 'time_part': time_part,
                                              'future_part': future_part})
            if dtobj != filtered_alarms[-1].datetime:
                response += ", "
            else:
                response += "."
            if alarm_count > 1 and dtobj == filtered_alarms[-2].datetime:
                response += " {} ".format(self.translation.get("and"))
        return response

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
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_alarms(), slots, siteid)

        if rc > 0:
            return None, self.error_sentence(rc, words_dict)

        alarm_count = len(filtered_alarms)
        if alarm_count == 0:
            response = self.translation.get("There is no alarm {room_part} {future_part} {time_part}.",
                                            {'room_part': words_dict['room_part'],
                                             'future_part': words_dict['future_part'],
                                             'time_part': words_dict['time_part']})
        elif alarm_count == 1:
            dtobj = filtered_alarms[0].datetime
            if words_dict['room_part']:
                room_part = ""
            else:
                room_part = self.get_roomstr([filtered_alarms[0].site], siteid)
            response = self.translation.get("Are you sure you want to delete the only "
                                            "alarm {room_slot} {future_part} at {h}:{min} {room_part}?",
                                            {'room_slot': words_dict['room_part'],
                                             'future_part': words_dict['future_part'],
                                             'h': ftime.get_alarm_hour(dtobj),
                                             'min': ftime.get_alarm_minute(dtobj),
                                             'room_part': room_part})
        else:
            response = self.translation.get("There are {future_part} {time_part} {room_part} {num} alarms. "
                                            "Are you sure?",
                                            {'future_part': words_dict['future_part'],
                                             'time_part': words_dict['time_part'],
                                             'room_part': words_dict['room_part'],
                                             'num': alarm_count})
        return filtered_alarms, self.del_multi_spaces(response)

    def delete_alarms(self, slots, siteid):

        """
        Removes all alarms in the list "alarms_delete".
        :return: String "Done."
        """
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_alarms(), slots, siteid)
        self.alarmctl.delete_multi(filtered_alarms)
        return self.translation.get("Done.")

    def answer_alarm(self, slots, siteid):
        # TODO: translation
        # TODO: self.config[snooze_config] = {state: on, default_duration: 9, min_duration: 2, max_duration: 10,
        #                                     challenge: on}

        if not slots:
            self.translation.get("I'm afraid I didn't understand you.")

        min_duration = self.config['snooze_config']['min_duration']
        max_duration = self.config['snooze_config']['max_duration']
        if slots.get('duration') and min_duration <= int(slots['duration']['minutes']) <= max_duration:
            duration = int(slots['duration']['minutes'])
        else:
            duration = self.config['snooze_config']['default_duration']
        dtobj_next = self.temp_memory[siteid]['alarm'] + datetime.timedelta(minutes=duration)
        next_alarm = Alarm(dtobj_next, self.alarmctl.sites_dict[siteid])

        if 'answer' in slots.keys():
            answer_slot = slots['answer']
        else:
            answer_slot = None

        if not answer_slot or answer_slot == "snooze":
            self.alarmctl.add(next_alarm)
            return "Ich wecke dich wieder in {min} Minuten.".format(min=duration)

        elif slots['answer'] == "stop" and not self.config("challenge"):
            return "Ich wecke dich in 4 Minuten."
        else:
            return "Ich wecke dich in 5 Minuten."

    def filter_alarms(self, alarms, slots, siteid, timeslot_with_past=False):

        """Helper function which filters alarms with datetime and rooms"""

        future_part = ""
        time_part = ""
        room_part = ""
        # fill the list with all alarms and then filter it
        filtered_alarms = [alarm for alarm in alarms]
        dt_format = "%Y-%m-%d %H:%M"
        if 'time' in slots.keys():
            if slots['time']['kind'] == "InstantTime":
                alarm_time = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['value']), dt_format)
                future_part = self.get_time_description(alarm_time, only_days=True)
                if slots['time']['grain'] == "Hour" or slots['time']['grain'] == "Minute":
                    if not timeslot_with_past and ftime.get_delta_obj(alarm_time, only_date=False).days < 0:
                        return 1, None, None
                    filtered_alarms = [alarm for alarm in filtered_alarms
                                       if alarm.datetime == alarm_time]
                    time_part = self.translation.get("at {h}:{min}",
                                                     {'h': ftime.get_alarm_hour(alarm_time),
                                                      'min': ftime.get_alarm_minute(alarm_time)})
                else:
                    alarm_date = alarm_time.date()
                    if (alarm_date - datetime.datetime.now().date()).days < 0:
                        return 1, None, None
                    filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime.date() == alarm_date]
            elif slots['time']['kind'] == "TimeInterval":
                time_from = None
                time_to = None
                if slots['time']['from']:
                    time_from = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['from']), dt_format)
                if slots['time']['to']:
                    time_to = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['to']), dt_format)
                if not time_from and time_to:
                    filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime <= time_to]
                elif not time_to and time_from:
                    filtered_alarms = [alarm for alarm in filtered_alarms if time_from <= alarm.datetime]
                else:
                    filtered_alarms = [alarm for alarm in filtered_alarms if time_from <= alarm.datetime <= time_to]
                future_part = self.get_interval_part(time_from, time_to)
            else:
                return 2, None, None
        if 'room' in slots.keys():
            room_slot = slots['room']
            if room_slot == self.translation.get("here"):
                if siteid in self.dict_siteids.values():
                    context_siteid = siteid
                else:
                    return 3, None, None
            else:
                if room_slot in self.dict_siteids.keys():
                    context_siteid = self.dict_siteids[room_slot]
                else:
                    return 4, None, {'room': room_slot}
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.get_siteid() == context_siteid]
            room_part = self.get_roomstr([context_siteid], siteid)
        filtered_dtobjects_sorted = [alarm.datetime for alarm in filtered_alarms]
        filtered_dtobjects_sorted.sort()
        filtered_alarms_sorted = []
        for dtobject in filtered_dtobjects_sorted:
            alarms = [alarm for alarm in filtered_alarms if alarm.datetime == dtobject]
            for alarm in alarms:
                filtered_alarms_sorted.append(alarm)
        return 0, filtered_alarms_sorted, {'future_part': future_part, 'time_part': time_part, 'room_part': room_part}

    def error_sentence(self, rc, words_dict=None):
        if rc == 1:
            return self.translation.get("This time is in the past.")
        elif rc == 2:
            return self.translation.get("I'm afraid I didn't understand you.")
        elif rc == 3:
            return "{} {}".format(self.translation.get("This room here hasn't been configured yet."),
                                  self.translation.get("Please see the instructions for this alarm clock "
                                                       "app for how to add rooms."))
        elif rc == 4:
            if not words_dict:
                words_dict = {'room': ""}
            return "{} {}".format(self.translation.get("The room {room} has not been configured yet.",
                                                       {'room': words_dict['room']}),
                                  self.translation.get("Please see the instructions for this alarm clock "
                                                       "app for how to add rooms."))

    def get_roomstr(self, alarm_siteids, siteid):
        room_str = ""
        if len(self.alarmctl.sites_dict) > 1:
            for iter_siteid in alarm_siteids:
                if iter_siteid == siteid:
                    room_str += self.translation.get("here")
                else:
                    room = self.alarmctl.sites_dict[iter_siteid].room
                    current_room_prepos = self.translation.get_prepos(room)
                    room_str += "{prepos} {room}".format(prepos=current_room_prepos,
                                                         room=room)
                if len(alarm_siteids) > 1:
                    if iter_siteid != alarm_siteids[-1] and iter_siteid != alarm_siteids[-2]:
                        room_str += ", "
                    if iter_siteid == alarm_siteids[-2]:
                        room_str += " {and_word} ".format(and_word=self.translation.get("and"))
        return room_str

    def get_time_description(self, alarm_time, only_days=False):
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        alarm_weekday = self.translation.get(weekdays[alarm_time.weekday()])
        delta_days = (alarm_time - ftime.get_now_time()).days
        delta_hours = (alarm_time - ftime.get_now_time()).seconds // 3600
        if (delta_days == 0 or delta_hours <= 12) and not only_days:
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
        elif delta_days == -1 and (alarm_time.date() - datetime.datetime.now().date()).days == 0:
            delta_hours = (ftime.get_now_time() - alarm_time).seconds // 3600
            return self.translation.get("{delta_hours} hours ago", {'delta_hours': delta_hours})
        elif delta_days == -1 and (alarm_time.date() - datetime.datetime.now().date()).days == -1:
            return self.translation.get("yesterday")
        elif delta_days == 2:
            return self.translation.get("the day after tomorrow")
        elif 3 <= delta_days <= 6:
            return self.translation.get("on {weekday}", {'weekday': alarm_weekday})
        elif delta_days == 7:
            return self.translation.get("on {weekday} in exactly one week", {'weekday': alarm_weekday})
        elif delta_days <= -2:
            return self.translation.get("{delta_days} days ago", {'delta_days': delta_days})
        else:
            return self.translation.get("in {delta_days} days, on {weekday}, the {day}.{month}.",
                                        {'delta_days': delta_days, 'weekday': alarm_weekday,
                                         'day': int(alarm_time.day), 'month': int(alarm_time.month)})

    def get_interval_part(self, from_time, to_time):
        if to_time:
            if to_time.date() != ftime.get_now_time().date():
                future_part_to = self.get_time_description(to_time, only_days=True)
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
                future_part_from = self.get_time_description(from_time, only_days=True)
            else:
                future_part_from = ""
            h_from = ftime.get_alarm_hour(from_time)
            min_from = ftime.get_alarm_minute(from_time)
            from_part = self.translation.get("{from_word} {future_part_from} {h_from}:{min_from}",
                                             {'from_word': from_word, 'future_part_from': future_part_from,
                                              'h_from': h_from, 'min_from': min_from})
        else:
            from_part = ""
        return "{} {}".format(from_part, to_part)

    def error_understanding(self):
        return self.translation.get("Sorry, I did not understand you.")

    @staticmethod
    def del_multi_spaces(sentence):
        return " ".join(sentence.split())
