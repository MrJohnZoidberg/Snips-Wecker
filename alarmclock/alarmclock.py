# -*- coding: utf-8 -*-
#                                      Explanations:
import datetime                        # date and time
import paho.mqtt.client as mqtt        # sending mqtt messages
import json                            # payload in mqtt messages
from . import utils                    # utils.py
from . alarm import Alarm, AlarmControl
from . translation import _, ngettext, preposition, humanize, spoken_time, get_interval_part


def concat( *strings):
    return " ".join( strings)


def parse( time_str):
    return datetime.datetime.strptime( time_str[:16], "%Y-%m-%d %H:%M")


def get_now_time():
    dt = datetime.datetime.now()
    return datetime.datetime( dt.year, dt.month, dt.day, dt.hour, dt.minute)


class AlarmClock:
    
    def __init__( self, mqtt_client):
        self.config = utils.get_config("config.ini")
        self.remembered_slots = {}
        self.alarmctl = AlarmControl( self.config, mqtt_client)


    def new_alarm( self, slots, siteid):

        """
        Called when creating a new alarm. Logic: see ../resources/Snips-Alarmclock-newAlarm.png
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

        if not slots: return _("Sorry, I did not understand you.")

        if len( self.alarmctl.sites_dict) > 1:
            if 'room' in slots:
                room_slot = slots['room']
                if room_slot == _("here"):
                    if siteid not in self.config['dict_siteids'].values():
                        return _("This room here hasn't been configured yet.")
                    alarm_site_id = siteid
                    room_part = _("here")

                else:
                    if room_slot not in self.config['dict_siteids']:
                        return _("The room {room} has not been configured yet.").format( room=room_slot)
                    alarm_site_id = self.config['dict_siteids'][room_slot]
                    if siteid == self.config['dict_siteids'][room_slot]:
                        room_part = _("here")
                    else:
                        room_part = preposition(room_slot)

            else:
                alarm_site_id = self.config['dict_siteids'][self.config['default_room']]
                if siteid == self.config['dict_siteids'][self.config['default_room']]:
                    room_part = _("here")
                else:
                    room_part = preposition( self.config['default_room'])
        else:
            alarm_site_id = self.config['dict_siteids'][self.config['default_room']]
            room_part = ""
            
        # remove the timezone and some numbers from time string
        if slots['time']['kind'] != "InstantTime":
            return _("I'm afraid I did not understand you.")
        alarm_time = parse(slots['time']['value'])

        if (alarm_time - get_now_time()).days < 0:  # if date is in the past
            return concat( _("This time is in the past."),
                           _("Please set another alarm."))
        elif (alarm_time - get_now_time()).seconds < 120:
            return concat( _("This alarm would ring now."),
                           _("Please set another alarm."))

        alarm = Alarm(alarm_time, self.alarmctl.sites_dict[alarm_site_id], repetition=None)
        self.alarmctl.add(alarm)
                                             
        return _("The alarm will ring {room_part} {future_part} at {time}.").format(
            future_part=humanize(alarm_time),
            time=spoken_time(alarm_time),
            room_part=room_part)


    def get_alarms( self, slots, siteid):
        error, alarms, words_dict = self.filter_alarms( self.alarmctl.get_alarms(), slots, siteid)
        if error: return error

        alarm_count = len(alarms)
        if alarm_count == 0:
            response = _("There no alarm is {room_part} {future_part} {time_part}.")
            
        else:
            response = ngettext( 
                "There is one alarm {room_part} {future_part} {time_part}.",
                "There are {num_part} alarms {room_part} {future_part} {time_part}.", alarm_count)
        
        response = response.format( num_part=alarm_count,
            room_part=words_dict['room_part'],
            future_part=words_dict['future_part'],
            time_part=words_dict['time_part'])

        if alarm_count > 5:
            response += _(" The next five are: ")
            alarms = alarms[:5]

        return response + self.add_alarms_part( siteid, alarms, words_dict, alarm_count)


    def get_next_alarm( self, slots, siteid):
        error, alarms, words_dict = self.filter_alarms( self.alarmctl.get_alarms(), slots, siteid)
        if error: return error

        if not alarms:
            return _("There is no alarm {room_part} {future_part} {time_part}").format(
                        room_part=words_dict['room_part'],
                        future_part=words_dict['future_part'],
                        time_part=words_dict['time_part'])

        next_alarm = alarms[0]
        if words_dict['room_part']:
            room_part = ""
        else:
            room_part = self.get_roomstr([next_alarm.site.siteid], siteid)
            
        return _("The next alarm {room_slot} starts {future_part} at {time} {room_part}.").format(
                    room_slot=words_dict['room_part'],
                    future_part=humanize(next_alarm.datetime),
                    time=spoken_time(next_alarm.datetime),
                    room_part=room_part)


    def get_missed_alarms( self, slots, siteid):
        error, alarms, words_dict = self.filter_alarms(
            self.alarmctl.get_missed_alarms(), slots, siteid, timeslot_with_past=True)
        if error: return error

        alarm_count = len(alarms)
        if alarm_count == 0:
            response = _("You missed no alarm {room_part} {future_part} {time_part}")
        else:
            response = ngettext(
                "You missed one alarm {room_part} {future_part} {time_part}",
                "You missed {num} alarms {room_part} {future_part} {time_part}.")
        
        response = response.format( num=alarm_count,
                room_part=words_dict['room_part'],
                future_part=words_dict['future_part'],
                time_part=words_dict['time_part'])
                
        alarms = alarms.sorted( reverse=True)  # sort from old to new (say oldest alarms first)
        response += self.add_alarms_part( siteid, alarms, words_dict, alarm_count)
        self.alarmctl.delete_alarms( alarms)
        return response


    def add_alarms_part( self, siteid, alarms, words_dict, alarm_count):
        response = " "
        for alarm in alarms:

            # If room and/or time not said in speech command, the alarms were not filtered with that.
            # So these parts must be looked up for every datetime object.
            future_part = words_dict.get( 'future_part')
            if not future_part:
                future_part = humanize(alarm.datetime, only_days=True)

            time_part = words_dict.get( 'time_part')
            if not time_part:
                time_part = _("at {time}").format( time=spoken_time(alarm.datetime))
                
            room_part = words_dict.get( 'room_part')
            if not room_part:
                room_part = self.get_roomstr( [
                    alarm.site.siteid for alarm in
                    self.alarmctl.get_alarms(alarm.datetime)], siteid)
                
            response += _("{future_part} {time_part} {room_part}").format( locals())        
            response += ", " if alarm.datetime != alarms[-1].datetime else "."
            if alarm_count > 1 and alarm.datetime == alarms[-2].datetime:
                response += _(" and ")
        return response.strip()


    def delete_alarms_try( self, slots, siteid):
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
        error, alarms, words_dict = self.filter_alarms( self.alarmctl.get_alarms(), slots, siteid)
        if error: return [], error

        if not alarms:
            return [], _("There is no alarm {room_part} {future_part} {time_part}.").format(
                            room_part=words_dict['room_part'],
                            future_part=words_dict['future_part'],
                            time_part=words_dict['time_part'])
                            
        alarm_count = len(alarms)
        if alarm_count == 1:
            if words_dict['room_part']:
                room_part = ""
            else:
                room_part = self.get_roomstr([alarms[0].site], siteid)
                
            return alarms, _("Are you sure you want to delete the only "
                             "alarm {room_slot} {future_part} at {time} {room_part}?").format(
                                room_slot=words_dict['room_part'],
                                future_part=words_dict['future_part'],
                                time=spoken_time( alarms[0].datetime),
                                room_part=room_part)
                                
        return alarms, _("There are {future_part} {time_part} {room_part} {num} alarms. "
                         "Are you sure?").format(
                            future_part=words_dict['future_part'],
                            time_part=words_dict['time_part'],
                            room_part=words_dict['room_part'],
                            num=alarm_count)


    def delete_alarms( self, slots, siteid):

        """
        Removes all alarms in the list "alarms_delete".
        :return: String "Done."
        """
        rc, alarms, words_dict = self.filter_alarms( self.alarmctl.get_alarms(), slots, siteid)
        self.alarmctl.delete_alarms(alarms)
        return _("Done.")


    def answer_alarm( self, slots, siteid):
        # TODO: self.config[snooze_config] = {state: on, default_duration: 9, min_duration: 2, max_duration: 10,
        #                                     challenge: on}

        if not slots: return _("I'm afraid I did not understand you.")

        min_duration = self.config['snooze_config']['min_duration']
        max_duration = self.config['snooze_config']['max_duration']
        if slots.get('duration') and min_duration <= int(slots['duration']['minutes']) <= max_duration:
            duration = int(slots['duration']['minutes'])
        else:
            duration = self.config['snooze_config']['default_duration']
        dtobj_next = self.alarmctl.temp_memory[siteid] + datetime.timedelta(minutes=duration)
        next_alarm = Alarm(dtobj_next, self.alarmctl.sites_dict[siteid])

        answer_slot = slots['answer'] if 'answer' in slots else None

        if not answer_slot or answer_slot == "snooze":
            self.alarmctl.add( next_alarm)
            return _("I will wake you in {min} minutes.").format(min=duration)

        return _("I will wake you in {min} minutes.").format( min=5)


    def filter_alarms( self, alarms, slots, siteid, timeslot_with_past=False):
        """Helper function which filters alarms with datetime and rooms"""

        future_part = ""
        time_part = ""
        room_part = ""

        if 'time' in slots:
            if slots['time']['kind'] == "InstantTime":
                alarm_time = parse(slots['time']['value'])
                future_part = humanize(alarm_time, only_days=True)
                
                if slots['time']['grain'] == "Hour" or slots['time']['grain'] == "Minute":
                    if not timeslot_with_past and (alarm_time - get_now_time()).days < 0:
                        return 1, None, None
                    alarms = filter( lambda a: a.datetime == alarm_time, alarms)
                    time_part = _("at {time}").format( time=spoken_time(alarm_time))

                else:
                    alarm_date = alarm_time.date()
                    if (alarm_date - datetime.datetime.now().date()).days < 0:
                        return _("This time is in the past."), [], {}
                    alarms = filter( lambda a: a.datetime.date() == alarm_date, alarms)
            
            elif slots['time']['kind'] == "TimeInterval":
                time_from = None
                time_to = None
                if slots['time']['from']:
                    time_from = parse(slots['time']['from'])
                if slots['time']['to']:
                    time_to = parse(slots['time']['to'])
                if not time_from and time_to:
                    alarms = filter( lambda a: a.datetime <= time_to, alarms)
                elif time_from and not time_to:
                    alarms = filter( lambda a: time_from <= a.datetime, alarms)
                else:
                    alarms = filter( lambda a: time_from <= a.datetime <= time_to, alarms)
                future_part = get_interval_part( time_from, time_to)
                
            else:
                return _("I'm afraid I did not understand you."), [], {}
                
        if 'room' in slots:
            room_slot = slots['room']
            if room_slot == _("here"):
                if siteid not in self.config['dict_siteids'].values():
                    return _("This room has not been configured yet."), [], {}
                context_siteid = siteid
                    
            else:
                if room_slot not in self.config['dict_siteids']:
                    return _("The room {room} has not been configured yet.").format( room=room_slot), [], {}
                context_siteid = self.config['dict_siteids'][room_slot]
                    
            alarms = filter( lambda a: a.get_siteid() == context_siteid, alarms)
            room_part = self.get_roomstr([context_siteid], siteid)
            
        alarms = sorted( alarms, key=lambda alarm: alarm.datetime)
        return "", alarms, {
            'future_part': future_part,
            'time_part': time_part,
            'room_part': room_part
        }


    def get_roomstr( self, siteids, siteid):
        room_str = ""
        if len( self.alarmctl.sites_dict) > 1:
            for iter_siteid in siteids:
                if iter_siteid == siteid:
                    room_str += _("here")
                else:
                    room_str += preposition( self.alarmctl.sites_dict[iter_siteid].room)

                if len(siteids) > 1:
                    if iter_siteid == siteids[-2]: room_str += _(" and ")
                    elif iter_siteid != siteids[-1]: room_str += ", "
        return room_str
