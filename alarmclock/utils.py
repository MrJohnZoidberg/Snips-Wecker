# -*- coding: utf-8 -*-

import ConfigParser
from pydub import AudioSegment       # change volume of ringtone
import ast                           # convert string to dictionary
import io                            # opening alarm list or config file
import json                          # dictionary to file


class SnipsConfigParser(ConfigParser.SafeConfigParser):
    def to_dict(self):
        return {section: {
            option_name: option for option_name, option in self.items(section)
        } for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding="utf-8") as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, ConfigParser.Error):
        return dict()


def get_ringvol(config):
    ringvol = config['global']['ringing_volume']
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
    ringtmo = config['global']['ringing_timeout']
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
    dsiteid = config['global']['dict_site-id']
    if not dsiteid:
        dsiteid = {'Schlafzimmer': 'default'}
    else:
        dsiteid = ast.literal_eval(dsiteid)
    return dsiteid


def get_dprepos(config):
    dprepos = config['global']['german_prepositions']
    if not dprepos:
        dprepos = {'Schlafzimmer': 'im'}
    else:
        dprepos = ast.literal_eval(dprepos)
    return dprepos


def get_dfroom(config):
    dfroom = config['global']['default_room']
    if not dfroom:
        dfroom = "Schlafzimmer"
    return dfroom


def edit_volume(sound_file, volume):
    ringtone = AudioSegment.from_wav(sound_file)
    ringtone -= ringtone.max_dBFS
    calc_volume = (100 - (volume * 0.8 + 20)) * 0.6
    ringtone -= calc_volume
    wav_file = open(".temporary_ringtone", "r+w")
    ringtone.export(wav_file, format='wav')
    wav_file.seek(0)
    ringtone_wav = wav_file.read()
    wav_file.close()
    return ringtone_wav


def save_alarms(alarms, path):
    json_alarms = json.dumps(alarms).encode('utf8')
    with io.open(path, "w") as f:
        # TODO: TypeError: write() argument 1 must be unicode, not str
        f.write(json_alarms)
