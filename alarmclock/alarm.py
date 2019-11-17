import datetime


class Alarm:
    def __init__(self, datetime_obj=None, site=None, repetition=None, missed=False):
        self.datetime = datetime_obj
        self.repetition = repetition
        self.site = site
        self.missed = missed
        self.passed = False
        self.ringing = False

    def set_datetime_str(self, datetime_str, str_format="%Y-%m-%d %H:%M"):
        self.datetime = datetime.datetime.strptime(datetime_str, str_format)

    def get_datetime_str(self, str_format="%Y-%m-%d %H:%M"):
        return datetime.datetime.strftime(self.datetime, str_format)

    def get_data_dict(self):
        return {'datetime': self.get_datetime_str(),
                'siteid': self.site.siteid,
                'room': self.site.room,
                'repetition': self.repetition,
                'missed': self.missed}

    def check_missed(self):
        return (self.datetime - datetime.datetime.now()).days < 0
