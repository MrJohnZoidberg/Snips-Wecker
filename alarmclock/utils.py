# -*- coding: utf-8 -*-

from pydub import AudioSegment       # change volume of ringtone


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
    if ringtone_str == "off":
        ringtone_status = False
    else:
        ringtone_status = True
    return ringtone_status


def get_snoozestat(config):
    snooze_str = config['global']['snooze_status'].encode('utf8')
    if snooze_str == "off":
        snooze_status = False
    else:
        snooze_status = True
    return snooze_status


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
