# -*- coding: utf-8 -*-

import datetime


def alarm_time_str(slots_time):
    # example string: "2015-04-08 09:39:00 +02:00"
    return "{}:{}".format(slots_time.split(":")[0], slots_time.split(":")[1])


def get_now_time(day_format=0):
    now = datetime.datetime.now()
    if day_format == 0:
        now_time_str = "{0}-{1}-{2} {3}:{4}".format(now.year, now.month, now.day, now.hour, now.minute)
        now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d %H:%M")
    else:
        now_time_str = "{0}-{1}-{2}".format(now.year, now.month, now.day)
        now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d")
    return now_time


def get_delta_days(alarm_time, day_format=0):
    delta_days = (alarm_time - get_now_time(day_format)).days  # calculate the days between alarm and now
    return delta_days


def get_alarm_hour(alarm_time):
    if alarm_time.hour == 1:  # word correction
        alarm_hour = "ein"
    else:
        alarm_hour = alarm_time.hour
    return alarm_hour


def get_alarm_minute(alarm_time):
    if alarm_time.minute == 0:  # gap correction in sentence
        alarm_minute = ""
    else:
        alarm_minute = alarm_time.minute
    return alarm_minute


def weekday(alarm_time):
    weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonnstag"]
    # The following must be "alarmtime.isoweekday()" if Sunday is your first day of the week
    alarm_weekday = weekdays[alarm_time.weekday()]  # pick the element from the list
    return alarm_weekday


def get_future_part(alarm_time, day_format=0):
    delta_days = get_delta_days(alarm_time, day_format=1)
    if delta_days == 0:
        if day_format == 0:
            delta_seconds = (alarm_time - get_now_time()).seconds
            delta_hours = delta_seconds // 3600
            minutes_remain = (delta_seconds % 3600) // 60
            if delta_hours == 1:  # for word fix in German
                hour_word = "Stunde"
                delta_hours = "einer"
            else:
                hour_word = "Stunden"
            if (delta_seconds // 3600) > 0:  # if delta_hours > 0 - not "delta_hours" because of string above
                if minutes_remain == 0:
                    future_part = "in {0} {1}".format(delta_hours, hour_word)
                else:
                    future_part = "in {0} {1} und {2} Minuten".format(delta_hours, hour_word, minutes_remain)
            else:
                if minutes_remain == 1:
                    future_part = "in einer Minute"
                else:
                    future_part = "in {0} Minuten".format(minutes_remain)
        else:
            future_part = "heute"
    elif delta_days == 1:
        future_part = "morgen"
    elif delta_days == 2:
        future_part = "übermorgen"
    elif 3 <= delta_days <= 6:
        future_part = "am kommenden {0}".format(weekday(alarm_time))
    elif delta_days == 7:
        future_part = "am {0} in genau einer Woche".format(weekday(alarm_time))
    else:
        future_part = "in {0} Tagen, am {1}, dem {2}.{3}.".format(delta_days, weekday(alarm_time),
                                                                  int(alarm_time.day),
                                                                  int(alarm_time.month))
    return future_part
