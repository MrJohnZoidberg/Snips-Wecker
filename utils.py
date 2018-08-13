# -*- coding: utf-8 -*-

from pydub import AudioSegment       # change volume of ringtone
import ast                           # convert string to dictionary
import io                            # opening alarm list file
import json                          # dictionary to file


class Utils:
    def __init__(self, config):
        self.config = config

    def get_ringvol(self):
        ringvol = self.config['global']['ringing_volume']
        if not ringvol:  # if dictionaray not filled with values
            ringvol = 50
        else:
            ringvol = int(ringvol)
            if ringvol < 0:
                ringvol = 0
            elif ringvol > 100:
                ringvol = 100
        return ringvol

    def get_ringtmo(self):
        ringtmo = self.config['global']['ringing_timeout']
        if not ringtmo:
            ringtmo = 30
        else:
            if str(ringtmo)[-1] == "s":
                ringtmo = str(ringtmo)[:-1]
                ringtmo = int(ringtmo)
            if ringtmo < 5:
                ringtmo = 5
        return ringtmo

    def get_dsiteid(self):
        dsiteid = self.config['global']['dict_site-id']
        if not dsiteid:
            dsiteid = {'default': 'Schlafzimmer'}
        else:
            dsiteid = ast.literal_eval(dsiteid)
        return dsiteid

    def get_dfsiteid(self):
        dfsiteid = self.config['global']['default_site-id']
        if not dfsiteid:
            dfsiteid = "Schlafzimmer"
        return dfsiteid

    @staticmethod
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

    @staticmethod
    def save_alarms(alarms, path):
        json_alarms = json.dumps(alarms)
        with io.open(path, "w") as f:
            f.write(json_alarms)
