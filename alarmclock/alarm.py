import datetime
from . import formattime as ftime


class Alarm:
    def __init__(self, site, datetime_obj=None):
        self.datetime = datetime_obj
        self.site = site
        self.ringing = False
        self.sun_rising = False

    @property
    def datetime_str(self, str_format="%Y-%m-%d %H:%M"):
        return datetime.datetime.strftime(self.datetime, str_format)

    @datetime_str.setter
    def datetime_str(self, datetime_str, str_format="%Y-%m-%d %H:%M"):
        self.datetime = datetime.datetime.strptime(datetime_str, str_format)

    @property
    def passed(self):
        return self.datetime < datetime.datetime.now()

    @property
    def seconds_to(self):
        return int((self.datetime - datetime.datetime.now()).total_seconds())

    @property
    def data_dict(self):
        return {'datetime': self.datetime_str,
                'siteid': self.site.siteid,
                'room': self.site.room}

    @property
    def hour(self):
        return ftime.get_alarm_hour(self.datetime)

    @property
    def minute(self):
        return ftime.get_alarm_minute(self.datetime)
