# -*- coding: utf-8 -*-

from pydub import AudioSegment       # change volume of ringtone
import re
import configparser
import io
import wave
import struct
from collections import namedtuple
from builtins import max as builtin_max


ON_OFF = {
    'on'  : True,
    'off' : False,
}

def read_configuration_file(configuration_file):
    cp = configparser.ConfigParser()
    with io.open(configuration_file, encoding="utf-8") as f:
        cp.read_file(f)
    return {section: {option_name: option for option_name, option in cp.items(section)}
            for section in cp.sections()}


def get_config(configuration_file):
    config = read_configuration_file(configuration_file)
    output_dict = dict()
    output_dict['dict_siteids'] = _get_dict_siteids(config)
    del config['global']['dict_siteids']
    for param in config['global']:
        user_value = config['global'][param].replace(" ", "")
        print( param, user_value)
        output_dict[param] = {}
        for pair in user_value.split(","):
            fvalue = _format_value(param, pair.split(":")[1])
            output_dict[param][pair.split(":")[0]] = fvalue
        if param in ('ringing_volume', 'ringing_timeout', 'ringtone_status'):
            output_dict[param] = {
                output_dict['dict_siteids'][room]: _format_value(param, user_value)
                for room in output_dict['dict_siteids'] }
        else:
            output_dict[param] = _format_value(param, user_value)
    print( output_dict)
    return output_dict


def _get_dict_siteids(config):
    pairs = config['global']['dict_siteids'].replace(" ", "").split(",")
    return { room : site_id
        for room, site_id in map( lambda pair: pair.split(":"), pairs) }


def _format_value( param, user_value):
    
    if param == 'ringing_volume' or param == 'ringing_timeout':
        return int(user_value)

    elif param == 'default_room':
        # TODO: Make room names with spaces valid.
        return user_value

    elif param in ('ringtone_status', 'restore_alarms'):
        return bool( re.findall("^(yes|on|true)$", user_value.lower()))

    elif param == 'snooze_config':
        return { option : ON_OFF.get( value, value) if option == 'state' else value
            for option, value in map( lambda pair: pair.split(":"), pairs) }


def edit_volume( wav_path, volume):
    ringtone = AudioSegment.from_wav(wav_path)
    ringtone -= ringtone.max_dBFS
    calc_volume = (100 - (volume * 0.8 + 20)) * 0.6
    ringtone -= calc_volume

    with wave.open( ".temporary_ringtone", 'wb') as wave_data:
        wave_data.setnchannels(ringtone.channels)
        wave_data.setsampwidth(ringtone.sample_width)
        wave_data.setframerate(ringtone.frame_rate)
        wave_data.setnframes(int(ringtone.frame_count()))
        wave_data.writeframesraw(ringtone._data)

    with open(".temporary_ringtone", "rb") as f:
        ringtone_wav = f.read()
    return ringtone_wav
