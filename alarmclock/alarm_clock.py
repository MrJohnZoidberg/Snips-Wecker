import datetime
from . import utils
from . import formattime as ftime
from .alarm import Alarm
from .alarmctl import AlarmControl

# Error values
CLOCK_ERR_TIME_PAST = 1
CLOCK_ERR_TIME_EARLY = 2
CLOCK_ERR_INSUFFICIENT_INFO = 3
CLOCK_ERR_ROOM = 4
CLOCK_ERR_NO_TIME = 5
CLOCK_ERR_NO_ROOMS = 6


def error_string(errno):
    """Return the error string associated with an alarm clock error number."""
    if errno == CLOCK_ERR_TIME_PAST:
        return "Diese Zeit liegt in der Vergangenheit."
    elif errno == CLOCK_ERR_TIME_EARLY:
        return "Dieser Alarm würde jetzt klingeln. Bitte stelle einen anderen Alarm."
    elif errno == CLOCK_ERR_INSUFFICIENT_INFO:
        return "Es wurden zu wenig Informationen gegeben."
    elif errno == CLOCK_ERR_ROOM:
        return "Der folgende Raum wurde noch nicht konfiguriert: "
    elif errno == CLOCK_ERR_NO_ROOMS:
        return "Es wurde noch kein Raum konfiguriert."
    elif errno == CLOCK_ERR_NO_TIME:
        return "Es wurde keine Zeit gegeben."
    else:
        return "Unbekannter Fehler."


class AlarmClock:
    def __init__(self, mqtt_client):
        self.config = utils.get_config("config.ini", "config.ini.default")
        self.dict_siteids = self.config['dict_siteids']  # format: { key=RoomName: value=siteId }
        self.default_room = self.config['default_room']
        self.alarmctl = AlarmControl(self.config, mqtt_client)  # Create alarmcontrol instance
        self.mqtt_client = mqtt_client

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
            return error_string(CLOCK_ERR_INSUFFICIENT_INFO)
        elif not self.alarmctl.sites_dict:
            return error_string(CLOCK_ERR_NO_ROOMS)

        if len(self.alarmctl.sites_dict) > 1:
            room_slot = slots.get('room')
            if room_slot:
                if room_slot == "hier":
                    if siteid not in self.dict_siteids.values():
                        return error_string(CLOCK_ERR_ROOM) + room_slot
                    alarm_site_id = siteid
                    room_part = room_slot
                else:
                    if room_slot not in self.dict_siteids.keys():
                        return error_string(CLOCK_ERR_ROOM) + room_slot
                    alarm_site_id = self.dict_siteids[room_slot]
                    if siteid == self.dict_siteids[room_slot]:
                        room_part = "hier"
                    else:
                        room_part = "im Raum {room}".format(room=room_slot)
            else:
                alarm_site_id = self.dict_siteids[self.default_room]
                if siteid == self.dict_siteids[self.default_room]:
                    room_part = "hier"
                else:
                    room_part = "im Raum {room}".format(room=self.default_room)
        else:
            alarm_site_id = self.dict_siteids[self.default_room]
            room_part = ""

        if slots['time']['kind'] != "InstantTime":
            return error_string(CLOCK_ERR_NO_TIME)

        alarm = Alarm(self.alarmctl.sites_dict[alarm_site_id], ftime.dtslot_to_dtobj(slots['time']['value']))
        if alarm.passed:
            return error_string(CLOCK_ERR_TIME_PAST)
        if alarm.seconds_to < 120:
            return error_string(CLOCK_ERR_TIME_EARLY)
        self.alarmctl.add(alarm)
        response = "Der Wecker wird {future_part} um {h} Uhr {min} {room_part} klingeln.".format(
            future_part=self.get_delta_description(alarm.datetime),
            h=alarm.hour,
            min=alarm.minute,
            room_part=room_part
        )
        return self.del_multi_spaces(response)

    def get_alarms(self, slots, siteid):
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_alarms(), slots, siteid)

        if rc > 0:
            if words_dict.get('room'):
                return error_string(rc) + words_dict.get('room')
            else:
                return error_string(rc)

        alarm_count = len(filtered_alarms)
        if alarm_count <= 1:
            if alarm_count == 0:
                count_part = "keine Alarme"
                end_part = "."
            else:
                count_part = "einen Alarm"
                end_part = " "
        else:
            count_part = "{num} Alarme".format(num=alarm_count)
            end_part = ". "
        response = "Es gibt {room_part} {future_part} {time_part} {num_part}{end}".format(
            room_part=words_dict['room_part'],
            future_part=words_dict['future_part'],
            time_part=words_dict['time_part'],
            num_part=count_part,
            end=end_part
        )
        if alarm_count > 5:
            response += "Die nächsten fünf sind: "
            filtered_alarms = filtered_alarms[:5]

        response = self.add_alarms_part(response, siteid, filtered_alarms, words_dict, alarm_count)
        return self.del_multi_spaces(response)

    def get_next_alarm(self, slots, siteid):
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_alarms(), slots, siteid)

        if rc > 0:
            if words_dict.get('room'):
                return error_string(rc) + words_dict.get('room')
            else:
                return error_string(rc)

        if filtered_alarms:
            next_alarm = filtered_alarms[0]

            if words_dict['room_part']:
                room_part = ""
            else:
                room_part = self.get_roomstr([next_alarm.site.siteid], siteid)
            response = "Der nächste Alarm {room_slot} startet {future_part} um {h} Uhr {min} {room_part}.".format(
                room_slot=words_dict['room_part'],
                future_part=self.get_delta_description(next_alarm.datetime),
                h=ftime.get_alarm_hour(next_alarm.datetime),
                min=ftime.get_alarm_minute(next_alarm.datetime),
                room_part=room_part
            )
        else:
            response = "Es gibt {room_part} {future_part} {time_part} {num_part}{end}".format(
                room_part=words_dict['room_part'],
                future_part=words_dict['future_part'],
                time_part=words_dict['time_part'],
                num_part="keine Alarme",
                end="."
            )
        return self.del_multi_spaces(response)

    def get_missed_alarms(self, slots, siteid):
        rc, filtered_alarms, words_dict = self.filter_alarms(self.alarmctl.get_missed_alarms(),
                                                             slots, siteid, timeslot_with_past=True)
        if rc > 0:
            if words_dict.get('room'):
                return error_string(rc) + words_dict.get('room')
            else:
                return error_string(rc)

        filtered_alarms.sort(reverse=True)  # sort from old to new (say oldest alarms first)

        alarm_count = len(filtered_alarms)
        if alarm_count <= 1:
            if alarm_count == 0:
                count_part = "keinen Alarm"
                end_part = "."
            else:
                count_part = "einen Alarm"
                end_part = " "
        else:
            count_part = "{num} Alarme".format(num=alarm_count)
            end_part = ". "
        response = "Du hast {room_part} {future_part} {time_part} {num_part} verpasst{end}".format(
            room_part=words_dict['room_part'],
            future_part=words_dict['future_part'],
            time_part=words_dict['time_part'],
            num_part=count_part,
            end=end_part
        )
        response = self.add_alarms_part(response, siteid, filtered_alarms, words_dict, alarm_count)
        self.alarmctl.delete_multi(filtered_alarms)  # Like a mailbox: Say missed messages and delete them after that.
        return self.del_multi_spaces(response)

    def add_alarms_part(self, response, siteid, filtered_alarms, words_dict, alarm_count):
        for alarm in filtered_alarms:
            dtobj = alarm.datetime
            # If room and/or time not said in speech command, the alarms were not filtered with that.
            # So these parts must be looked up for every datetime object.
            if not words_dict['future_part']:
                future_part = alarm.delta_description(only_days=True)
            else:
                future_part = ""
            if words_dict['time_part']:
                time_part = ""
            else:
                time_part = "um {h}:{min}".format(
                    h=ftime.get_alarm_hour(dtobj),
                    min=ftime.get_alarm_minute(dtobj)
                )
            if not words_dict['room_part']:
                room_part = self.get_roomstr([alarm.site.siteid for alarm in self.alarmctl.get_alarms(dtobj)], siteid)
            else:
                room_part = ""
            response += "{future_part} {time_part} {room_part}".format(
                future_part=future_part,
                time_part=time_part,
                room_part=room_part
            )
            if dtobj != filtered_alarms[-1].datetime:
                response += ", "
            else:
                response += "."
            if alarm_count > 1 and dtobj == filtered_alarms[-2].datetime:
                response += " und "
        return response

    def delete_alarms(self, slots, siteid):
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
            if words_dict.get('room'):
                return error_string(rc) + words_dict.get('room')
            else:
                return error_string(rc)

        alarm_count = len(filtered_alarms)
        if alarm_count == 0:
            sentence = "Es gibt {room_part} {future_part} {time_part} keinen Alarm.".format(
                room_part=words_dict['room_part'],
                future_part=words_dict['future_part'],
                time_part=words_dict['time_part']
            )
        elif alarm_count == 1:
            dtobj = filtered_alarms[0].datetime
            if words_dict['room_part']:
                room_part = ""
            else:
                room_part = self.get_roomstr([filtered_alarms[0].site], siteid)
            self.alarmctl.delete_multi(filtered_alarms)
            sentence = "Der einzige Alarm {room_slot} {future_part} um {h} Uhr {min} {room_part} wurde gelöscht."
            sentence.format(
                room_slot=words_dict['room_part'],
                future_part=words_dict['future_part'],
                h=ftime.get_alarm_hour(dtobj),
                min=ftime.get_alarm_minute(dtobj),
                room_part=room_part
            )
        else:
            self.alarmctl.delete_multi(filtered_alarms)
            sentence = "Es wurden {num} Alarme {future_part} {time_part} {room_part} gelöscht.".format(
                num=alarm_count,
                future_part=words_dict['future_part'],
                time_part=words_dict['time_part'],
                room_part=words_dict['room_part']
            )
        return self.del_multi_spaces(sentence)

    def filter_alarms(self, alarms, slots, siteid, timeslot_with_past=False):
        """Helper function which filters alarms with datetime and rooms"""
        future_part = ""
        time_part = ""
        room_part = ""
        # fill the list with all alarms and then filter it
        filtered_alarms = [alarm for alarm in alarms]
        dt_format = "%Y-%m-%d %H:%M"
        if slots.get('time'):
            if slots['time']['kind'] == "InstantTime":
                dtobj = ftime.dtslot_to_dtobj(slots['time']['value'])
                future_part = self.get_delta_description(dtobj, only_days=True)
                if slots['time']['grain'] in ['Hour', 'Minute', 'Second']:
                    if not timeslot_with_past and dtobj < datetime.datetime.now():
                        return CLOCK_ERR_TIME_PAST, None, None
                    filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime == dtobj]
                    time_part = "um {h}:{min}".format(h=ftime.get_alarm_hour(dtobj),
                                                      min=ftime.get_alarm_minute(dtobj))
                else:
                    if (dtobj.date() - datetime.datetime.now().date()).days < 0:
                        return CLOCK_ERR_TIME_PAST, None, None
                    filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime.date() == dtobj.date()]
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
                return CLOCK_ERR_NO_TIME, None, None
        if 'room' in slots.keys():
            room_slot = slots['room']
            if room_slot == "hier":
                if siteid not in self.dict_siteids.values():
                    return CLOCK_ERR_ROOM, None, None
                context_siteid = siteid
            else:
                if room_slot not in self.dict_siteids:
                    return CLOCK_ERR_ROOM, None, {'room': room_slot}
                context_siteid = self.dict_siteids[room_slot]

            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.get_siteid() == context_siteid]
            room_part = self.get_roomstr([context_siteid], siteid)
        filtered_dtobjects_sorted = [alarm.datetime for alarm in filtered_alarms]
        filtered_dtobjects_sorted.sort()
        filtered_alarms_sorted = list()
        for dtobject in filtered_dtobjects_sorted:
            alarms = [alarm for alarm in filtered_alarms if alarm.datetime == dtobject]
            for alarm in alarms:
                filtered_alarms_sorted.append(alarm)
        return 0, filtered_alarms_sorted, {'future_part': future_part, 'time_part': time_part, 'room_part': room_part}

    def get_roomstr(self, alarm_siteids, siteid):
        room_str = ""
        if len(self.alarmctl.sites_dict) > 1:
            for iter_siteid in alarm_siteids:
                if iter_siteid == siteid:
                    room_str += "hier"
                else:
                    room_str += "im Raum {room}".format(room=self.alarmctl.sites_dict[iter_siteid].room)
                if len(alarm_siteids) > 1:
                    if iter_siteid != alarm_siteids[-1] and iter_siteid != alarm_siteids[-2]:
                        room_str += ", "
                    if iter_siteid == alarm_siteids[-2]:
                        room_str += " und "
        return room_str

    def get_interval_part(self, from_time, to_time):
        if to_time:
            if to_time.date() != ftime.get_now_time().date():
                future_part_to = self.get_delta_description(to_time, only_days=True)
            else:
                future_part_to = ""
            h_to = ftime.get_alarm_hour(to_time)
            min_to = ftime.get_alarm_minute(to_time)
            from_word = "von"
            to_part = "bis {future_part_to} {h_to} Uhr {min_to}".format(
                future_part_to=future_part_to,
                h_to=h_to,
                min_to=min_to
            )
        else:
            from_word = "ab"
            to_part = ""
        if from_time:
            if from_time.date() != ftime.get_now_time().date():
                future_part_from = self.get_delta_description(from_time, only_days=True)
            else:
                future_part_from = ""
            h_from = ftime.get_alarm_hour(from_time)
            min_from = ftime.get_alarm_minute(from_time)
            from_part = "{from_word} {future_part_from} {h_from} Uhr {min_from}".format(
                from_word=from_word,
                future_part_from=future_part_from,
                h_from=h_from,
                min_from=min_from
            )
        else:
            from_part = ""
        return "{} {}".format(from_part, to_part)

    @staticmethod
    def del_multi_spaces(sentence):
        return " ".join(sentence.split())

    @staticmethod
    def get_delta_description(dtobj, only_days=False):
        weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        alarm_weekday = weekdays[dtobj.weekday()]
        delta_seconds = int(abs((dtobj - datetime.datetime.now()).total_seconds()))
        delta_minutes = delta_seconds // 60
        delta_hours = delta_minutes // 60
        delta_days = (dtobj.date() - datetime.datetime.now().date()).days()
        if not dtobj < datetime.datetime.now():
            if not only_days and delta_days == 0:
                minutes_remain = (delta_seconds % 3600) // 60
                if delta_hours == 1:  # for word fix in German
                    hour_words = "einer Stunde"
                else:
                    hour_words = "{delta_hours} Stunden".format(delta_hours=delta_hours)
                if minutes_remain == 1:
                    minute_words = "einer Minute"
                else:
                    minute_words = "{delta_minutes} Minuten".format(delta_minutes=minutes_remain)
                if delta_hours > 0 and minutes_remain == 0:
                    return "in {hour_part}".format(hour_part=hour_words)
                elif delta_hours > 0 and minutes_remain > 0:
                    return "in {hour_part} und {minute_part}".format(
                        hour_part=hour_words,
                        minute_part=minute_words
                    )
                else:
                    return "in {minute_part}".format(minute_part=minute_words)
            elif delta_days == 0:
                return "heute"
            elif delta_days == 1:
                return "morgen"
            elif delta_days == 2:
                return "übermorgen"
            elif 3 <= delta_days <= 6:
                return "am {weekday}".format(weekday=alarm_weekday)
            elif delta_days == 7:
                return "am {weekday} in einer Woche".format(weekday=alarm_weekday)
            else:
                return "in {delta_days} Tagen, am {weekday}, den {day}.{month}.".format(
                    delta_days=delta_days,
                    weekday=alarm_weekday,
                    day=dtobj.day,
                    month=dtobj.month
                )
        else:
            if delta_days == 0 and delta_hours == 0:
                if delta_minutes != 1:
                    return "vor {delta_minutes} Minuten".format(delta_minutes=abs(delta_minutes))
                else:
                    return "vor einer Minute"
            elif delta_days == 0:
                if delta_hours != 1:
                    return "vor {delta_hours} Stunden".format(delta_hours=delta_hours)
                else:
                    return "vor einer Stunde"
            elif delta_days == -1:
                return "gestern"
            else:
                return "vor {delta_days} Tagen".format(delta_days=delta_days)
