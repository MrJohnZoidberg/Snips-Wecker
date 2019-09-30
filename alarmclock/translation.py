# -*- coding: utf-8 -*-
import datetime, gettext, os
from arrow.locales import DeutschBaseLocale


LANGUAGE = "de"
LOCALES = os.path.join( os.path.dirname( __file__), 'locales')
TRANSLATION = gettext.translation( 'messages', localedir=LOCALES, languages=[LANGUAGE])
_ = TRANSLATION.gettext
ngettext = TRANSLATION.ngettext


WEEKDAYS = (
    _("monday"),   _("tuesday"), _("wednesday"),
    _("thursday"), _("friday"),  _("saturday"),
    _("sunday") )


def preposition( room):
    return ROOM_PREPOSITIONS_DE.get( room, "") + " " + room


ROOM_PREPOSITIONS_DE = {
    "Wartezimmer":      "im",
    "Eingang":          "im",
    "Gang":             "im",
    "Spielzimmer":      "im",
    "Garten":           "im",
    "Atrium":           "im",
    "Foyer":            "im",
    "Vestibül":         "im",
    "Büro":             "im",
    "Atelier":          "im",
    "Wintergarten":     "im",
    "Leitstand":        "im",
    "Konferenzraum":    "im",
    "Kesselhaus":       "im",
    "Umkleideraum":     "im",
    "Esszimmer":        "im",
    "Monteurzimmer":    "im",
    "Keller":           "im",
    "Arbeitszimmer":    "im",
    "Badezimmer":       "im",
    "Kinderzimmer":     "im",
    "Wohnzimmer":       "im",
    "Schlafzimmer":     "im",

    "Sauna":            "in der",
    "Toilette":         "in der",
    "Abstellkammer":    "in der",
    "Garage":           "in der",
    "Waschküche":       "in der",
    "Galerie":          "in der",
    "Aula":             "in der",
    "Cella":            "in der",
    "Kommandozentrale": "in der",
    "Speisekammer":     "in der",
    "Wartehalle":       "in der",
    "Küche":            "in der",

    "Dachboden":        "auf dem",
    "Balkon":           "auf dem",
}



def spoken_time( alarm_time):
    if alarm_time.hour == 1: hour = "ein"
    else: hour = alarm_time.hour
    
    if alarm_time.minute == 0: min = "" # gap correction in sentence
    elif alarm_time.minute == 1: min = "eins"
    else: min = alarm_time.minute
    
    return _("{min} minutes past {hour}").format( **locals())


def humanize( alarm_time, only_days=False):
    now = datetime.datetime.now()
    now = datetime.datetime( now.year, now.month, now.day, now.hour, now.minute)
    
    delta_days = (alarm_time - now).days
    delta_hours = (alarm_time - now).seconds // 3600
    if (delta_days == 0 or delta_hours <= 12) and not only_days:
        minutes_remain = ((alarm_time - now).seconds % 3600) // 60
        if delta_hours == 1:  # for word fix in German
            hour_words = _("in one hour")
        else:
            hour_words = _("in {hours} hours").format( hours=delta_hours)
            
        if minutes_remain == 1:
            minute_words = _("one minute")
        else:
            minute_words = _("{minutes} minutes").format( minutes=minutes_remain)
            
        if delta_hours > 0 and minutes_remain == 0: return hour_words
        if delta_hours > 0 and minutes_remain > 0:
            return _("{hours} and {minutes} minutes").format(
                hours_part=hour_words,
                minutes=minute_words)
        return _("in {minutes}").format(minutes=minute_words)
        
    if delta_days == 0: return _("today")
    if delta_days == 1: return _("tomorrow")
    if delta_days == 2: return _("the day after tomorrow")
    if delta_days == -1 and alarm_time.date() == now.date():
        delta_hours = (now - alarm_time).seconds // 3600
        return _("{hours} hours ago").format( hours=delta_hours)
    if delta_days == -1 and (alarm_time.date() - now.date()).days == -1:
        return _("yesterday")
    if delta_days <= -2: return _("{day_offset} days ago").format( day_offset=delta_days)
    
    alarm_weekday = DeutschBaseLocale.day_names[alarm_time.weekday()]
    if 3 <= delta_days <= 6: return _("on {weekday}").format( weekday=alarm_weekday)
    if delta_days == 7: return _("on {weekday} next week").format( weekday=alarm_weekday)

    return _("in {day_offset} days, on {weekday}, the {day}. {month}.").format( 
                day_offset=delta_days,
                weekday=alarm_weekday,
                day=alarm_time.day,
                month=DeutschBaseLocale.month_names[alarm_time.month])


def get_interval_part( from_time, to_time):

    to_part = ""
    from_word = _("as of")
    future_part_to = ""

    if to_time:
        from_word = _("from")
        if to_time.date() != get_now_time().date():
            future_part_to = humanize( to_time, only_days=True)
        to_part = _("to {future_part_to} {time}").format( 
                        future_part_to=future_part_to,
                        time=spoken_time(to_time))
        
    from_part = ""
    future_part_from = ""
    if from_time:
        if from_time.date() != get_now_time().date():
            future_part_from = humanize(from_time, only_days=True)

        from_part = _("{from_word} {future_part_from} {time}").format(
                         from_word=from_word,
                         future_part_from=future_part_from,
                         time=spoken_time(from_time))

    return from_part + " " + to_part
