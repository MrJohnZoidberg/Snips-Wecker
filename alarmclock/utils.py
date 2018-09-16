# -*- coding: utf-8 -*-

from pydub import AudioSegment       # change volume of ringtone
import formattime as ftime
import datetime


def get_ringvol(config):
    ringvol = config['global']['ringing_volume'].encode('utf8')
    if not ringvol:  # if dictionaray not filled with values
        ringvol = 50
    else:
        ringvol = int(ringvol)
        if ringvol < 0:
            ringvol = 0
        elif ringvol > 100:
            ringvol = 100
    return ringvol


def get_ringtmo(config):
    # Take 'm' and 'h' too
    ringtmo = config['global']['ringing_timeout'].encode('utf8')
    if not ringtmo:
        ringtmo = 30
    else:
        if str(ringtmo)[-1] == "s":
            ringtmo = str(ringtmo)[:-1]
            ringtmo = int(ringtmo)
        if ringtmo < 5:
            ringtmo = 5
    return ringtmo


def get_dsiteid(config):
    # TODO: Try with string ""
    dsiteid_str = config['global']['dict_site-id'].encode('utf8')
    if dsiteid_str:
        dsiteid_str.strip()
        pairs = dsiteid_str.split(",")
        dsiteid = {}
        for pair in pairs:
            stripped_pair = pair.strip()
            room, siteid = stripped_pair.split(":")
            dsiteid[room.strip()] = siteid.strip()
    else:
        dsiteid = {'Schlafzimmer': 'default'}
    return dsiteid


def get_prepos(room):
    room = room.lower()
    if "kammer" in room or room[-1] in ["e", "a"]:
        if "terasse" in room:
            prepos = "auf der"
        else:
            prepos = "in der"
    elif room[-1] in ["m", "r", "o", "g", "l", "d", "t", "n", "s", "h", "f", "c"]:
        if "unten" in room or "außen" in room:
            prepos = ""
        elif "boden" in room or room == "balkon":
            prepos = "auf dem"
        else:
            prepos = "im"
    else:
        prepos = "im Raum"
    return prepos


def get_dfroom(config):
    dfroom = config['global']['default_room'].encode('utf8')
    if not dfroom:
        dfroom = "Schlafzimmer"
    return dfroom


def get_restorestat(config):
    restore_str = config['global']['restore_alarms'].encode('utf8')
    if restore_str == "no":
        restore_status = False
    else:
        restore_status = True
    return restore_status


def get_ringtonestat(config):
    ringtone_str = config['global']['ringtone_status'].encode('utf8')
    if ringtone_str == "no":
        ringtone_status = False
    else:
        ringtone_status = True
    return ringtone_status


def edit_volume(wav_path, volume):
    # TODO: Change method so no error message (ffmpeg not found) in Snips anymore
    ringtone = AudioSegment.from_wav(wav_path)
    ringtone -= ringtone.max_dBFS
    calc_volume = (100 - (volume * 0.8 + 20)) * 0.6
    ringtone -= calc_volume
    wav_file = open(".temporary_ringtone", "r+w")
    ringtone.export(wav_file, format='wav')
    wav_file.seek(0)
    ringtone_wav = wav_file.read()
    wav_file.close()
    return ringtone_wav


def get_roomstr(alarm_siteids, dict_rooms, siteid):
    room_str = ""
    if len(dict_rooms) > 1:
        for iter_siteid in alarm_siteids:
            if iter_siteid == siteid:
                room_str += "hier"
            else:
                room_str += get_prepos(dict_rooms[iter_siteid]) + " " + dict_rooms[iter_siteid]
            if len(alarm_siteids) > 1:
                if iter_siteid != alarm_siteids[-1] and iter_siteid != alarm_siteids[-2]:
                    room_str += ", "
                if iter_siteid == alarm_siteids[-2]:
                    room_str += " und "
    return room_str


def filter_alarms(alarms, slots, siteid, dict_siteids):
    future_part = ""
    room_part = ""
    # fill the list with all alarms and then filter it
    filtered_alarms = {dtobj: alarms[dtobj] for dtobj in alarms}
    dt_format = "%Y-%m-%d %H:%M"
    if 'time' in slots.keys():
        if slots['time']['kind'] == "InstantTime":
            alarm_time = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['value']), dt_format)
            if ftime.get_delta_obj(alarm_time, only_date=False).days < 0:
                return {'rc': 1}
                # TODO
            future_part = ftime.get_future_part(alarm_time, only_date=True)
            if slots['time']['grain'] == "Hour":
                filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                   if dtobj.date() == alarm_time.date() and dtobj.hour == alarm_time.hour}
                future_part += " um {h} Uhr {min}".format(h=ftime.get_alarm_hour(alarm_time),
                                                          min=ftime.get_alarm_minute(alarm_time))
            elif slots['time']['grain'] == "Minute":
                filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                   if dtobj == alarm_time}
                future_part += " um {h} Uhr {min}".format(h=ftime.get_alarm_hour(alarm_time),
                                                          min=ftime.get_alarm_minute(alarm_time))
            else:
                filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                   if dtobj.date() == alarm_time.date()}
        elif slots['time']['kind'] == "TimeInterval":
            time_from = None
            time_to = None
            if slots['time']['from']:
                time_from = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['from']), dt_format)
            if slots['time']['to']:
                time_to = datetime.datetime.strptime(ftime.alarm_time_str(slots['time']['to']), dt_format)
                time_to = ftime.nlu_time_bug_bypass(time_to)  # NLU bug (only German): hour or minute too much
            if not time_from and time_to:
                filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms if dtobj <= time_to}
            elif not time_to and time_from:
                filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms if time_from <= dtobj}
            else:
                filtered_alarms = {dtobj: alarms[dtobj] for dtobj in filtered_alarms
                                   if time_from <= dtobj <= time_to}
            future_part = ftime.get_interval_part(time_from, time_to)
        else:
            return {'rc': 2}
    if 'room' in slots.keys():
        room_slot = slots['room']['value'].encode('utf8')
        if room_slot == "hier":
            if siteid in dict_siteids.values():
                context_siteid = siteid
            else:
                return {'rc': 3}
        else:
            if room_slot in dict_siteids.keys():
                context_siteid = dict_siteids[room_slot]
            else:
                return {'rc': 4, 'room': room_slot}
        filtered_alarms = {dtobj: [sid for sid in filtered_alarms[dtobj] if sid == context_siteid]
                           for dtobj in filtered_alarms}
        dict_rooms = {siteid: room for room, siteid in dict_siteids.iteritems()}
        room_part = get_roomstr([context_siteid], dict_rooms, siteid)
    filtered_alarms_sorted = [dtobj for dtobj in filtered_alarms if filtered_alarms[dtobj]]
    filtered_alarms_sorted.sort()
    alarm_count = len([sid for lst in filtered_alarms.itervalues() for sid in lst])
    return {
        'rc': 0,
        'filtered_alarms': filtered_alarms,
        'sorted_alarms': filtered_alarms_sorted,
        'alarm_count': alarm_count,
        'future_part': future_part,
        'room_part': room_part
    }
