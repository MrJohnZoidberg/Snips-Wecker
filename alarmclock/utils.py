from pydub import AudioSegment       # change volume of ringtone
import re
import configparser
import io
import wave


def read_configuration_file(configuration_file):
    try:
        cp = configparser.ConfigParser()
        with io.open(configuration_file, encoding="utf-8") as f:
            cp.read_file(f)
        return {section: {option_name: option for option_name, option in cp.items(section)}
                for section in cp.sections()}
    except (IOError, configparser.Error):
        return dict()


def get_config(configuration_file, default_configuration_file):
    config = read_configuration_file(configuration_file)
    default_config = read_configuration_file(default_configuration_file)
    output_dict = dict()
    output_dict['dict_siteids'], output_dict['default_room'] = _get_dict_siteids(config, default_config)
    del config['global']['dict_siteids']
    for param in config['global'].keys():
        user_value = config['global'][param].replace(" ", "")
        default_value = default_config['global'][param].replace(" ", "")
        if ":" in user_value:
            pairs = user_value.split(",")
            output_dict[param] = {}
            for pair in pairs:
                fvalue = _format_value(param, pair.split(":")[1], default_value)
                output_dict[param][pair.split(":")[0]] = fvalue
        elif param in ['ringing_volume', 'ringing_timeout']:
            output_dict[param] = {output_dict['dict_siteids'][room]: _format_value(param, user_value, default_value)
                                  for room in output_dict['dict_siteids']}
        else:
            output_dict[param] = _format_value(param, user_value, default_value)
    return output_dict


def _get_dict_siteids(config, default_config):
    user_value = config['global']['dict_siteids'].replace(" ", "")
    default_value = default_config['global']['dict_siteids'].replace(" ", "")
    fvalue = dict()
    default_room = None
    pairs = user_value.split(",")
    for pair in pairs:
        room, siteid = pair.split(":")
        fvalue[room] = siteid
        if pair == pairs[0]:
            default_room = room
    if not fvalue or not default_room:
        pairs = default_value.split(",")
        for pair in pairs:
            room, siteid = pair.split(":")
            fvalue[room] = siteid
            if pair == pairs[0]:
                default_room = room
        print("Invalid value in parameter 'dict_siteids' of config. Set to default.")
    return fvalue, default_room


def _format_value(param, user_value, default_value):
    set_default = False
    if param == 'ringing_volume':
        if re.findall("^(0?[0-9]?[0-9]|100)$", user_value):
            fvalue = int(user_value)
        else:
            fvalue = int(default_value)
            set_default = True

    elif param == 'ringing_timeout':
        # min: 3 sec - max: 8000 sec
        if re.findall("^([3-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-7][0-9][0-9][0-9]|8000)$", user_value):
            fvalue = int(user_value)
        else:
            fvalue = int(default_value)
            set_default = True

    else:
        fvalue = None
    if set_default:
        print("Invalid value in parameter '{}' of config. Set to default.".format(param))
    return fvalue


def edit_volume(wav_path, volume):
    ringtone = AudioSegment.from_wav(wav_path)
    ringtone -= ringtone.max_dBFS
    calc_volume = (100 - (volume * 0.8 + 20)) * 0.6
    ringtone -= calc_volume

    with wave.open(".temporary_ringtone", 'wb') as wave_data:
        wave_data.setnchannels(ringtone.channels)
        wave_data.setsampwidth(ringtone.sample_width)
        wave_data.setframerate(ringtone.frame_rate)
        wave_data.setnframes(int(ringtone.frame_count()))
        wave_data.writeframesraw(ringtone._data)

    with open(".temporary_ringtone", "rb") as f:
        ringtone_wav = f.read()
    return ringtone_wav
