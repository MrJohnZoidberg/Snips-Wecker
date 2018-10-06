# -*- coding: utf-8 -*-

from pydub import AudioSegment       # change volume of ringtone
import re


def get_config(config):
    config_dict = {}
    for param in config['global'].keys():
        plain_value = config['global'][param].encode('utf8')
        value = None

        if param == 'ringing_volume':
            value = "".join(re.findall("[0-9]", plain_value))
            if not value:  # if param not filled with values
                value = 50
            else:
                value = int(value)
                if value < 0:
                    value = 0
                elif value > 100:
                    value = 100

        elif param == 'ringing_timeout':
            value = "".join(re.findall("[0-9]", plain_value))
            unit = re.findall("[mh]", plain_value)
            if unit:
                unit = unit[-1]
            if not value:
                value = 30
            else:
                value = int(value)
            if unit == "m":
                value *= 60
            elif unit == "h":
                value *= 60
                value *= 60
            if value > 7200:  # max. is 2h
                value = 7200
            elif value < 5:
                value = 5

        elif param == 'dict_site-id':
            if plain_value:
                pairs = plain_value.strip().split(",")
                value = {}
                for pair in pairs:
                    stripped_pair = pair.strip()
                    room, siteid = stripped_pair.split(":")
                    value[room.strip()] = siteid.strip()
            else:
                value = {'Schlafzimmer': 'default'}

        elif param == 'default_room':
            value = plain_value.strip()
            if not value:
                value = "Schlafzimmer"

        elif param == 'restore_alarms' or param == 'ringtone_status':
            value = "".join(re.findall("[a-zA-Z]", plain_value))
            value = value.lower()
            if value == "no":
                value = False
            else:
                value = True

        elif param == 'snooze_config':
            if plain_value:
                pairs = plain_value.strip().split(",")
                value = {}
                for pair in pairs:
                    stripped_pair = pair.strip()
                    conf_param, conf_value = stripped_pair.split(":")
                    value[conf_param.strip().lower()] = conf_value.strip().lower()
                if 'state' in value.keys() and value['state']:
                    if value['state'] == "on":
                        value['state'] = True
                        if 'default_duration' in value.keys() and "".join(re.findall("[0-9]",
                                                                                     value['default_duration'])):
                            value['default_duration'] = int(value['default_duration'])
                            if value['default_duration'] < 2:
                                value['default_duration'] = 2
                            elif value['default_duration'] > 30:
                                value['default_duration'] = 30
                        else:
                            value['default_duration'] = 5

                        if 'challenge' in value.keys() and "".join(re.findall("[a-zA-z]", value['challenge'])):
                            if 'mode' not in value.keys() or not "".join(re.findall("[1-3]", value['mode'])):
                                value['mode'] = 1
                            if value['challenge'] == 'math' and not "".join(re.findall("[1-3]", value['difficulty'])):
                                value['difficulty'] = 1
                        else:
                            value['challenge'] = None
                    else:
                        value = {'state': False}
                else:
                    value = {'state': False}
            else:
                value = {'state': False}
        else:
            value = None
        config_dict[param] = value
    return config_dict


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
