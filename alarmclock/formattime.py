import datetime


def alarm_time_str(slots_time):
    # example input string: "2015-04-08 09:39:00 +02:00"
    # example return string: "2015-04-08 09:39"
    return "{}:{}".format(slots_time.split(":")[0], slots_time.split(":")[1])


def get_now_time(only_date=False):
    now = datetime.datetime.now()
    if only_date:
        now_time_str = "{0}-{1}-{2}".format(now.year, now.month, now.day)
        now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d")
    else:
        now_time_str = "{0}-{1}-{2} {3}:{4}".format(now.year, now.month, now.day, now.hour, now.minute)
        now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d %H:%M")
    return now_time


def get_delta_obj(alarm_time, only_date=False):
    delta_obj = (alarm_time - get_now_time(only_date))  # calculate the days between alarm and now
    return delta_obj


def get_alarm_hour(alarm_time):
    if alarm_time.hour == 1:  # word correction
        alarm_hour = "ein"
    else:
        alarm_hour = alarm_time.hour
    return alarm_hour


def get_alarm_minute(alarm_time):
    if alarm_time.minute == 0:  # gap correction in sentence
        alarm_minute = ""
    elif alarm_time.minute == 1:
        alarm_minute = "eins"
    else:
        alarm_minute = alarm_time.minute
    return alarm_minute
