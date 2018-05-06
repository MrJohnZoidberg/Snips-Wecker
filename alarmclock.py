import datetime
import time
import threading
import os
import subprocess
import pickle


class AlarmClock:
    def __init__(self, config):
        self.script_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
        alarmclock_config = config['Modules']['Alarmclock']
        self.saved_alarms_path = alarmclock_config['saved_alarms_path']
        self.ringing_volume = str(alarmclock_config['volume'])
        self.timeout = int(alarmclock_config['ringing_timeout'])
        open(self.saved_alarms_path, 'a').close()  # Create file, if not available
        self.alarms = self.read_alarms()  # read saved alarms from file
        self.save_alarms()  # because past alarms may have been deleted with self.read_alarms()
        self.format_time = self._FormatTime()
        self.slots = {}  # for confirmation before delete: slots -> self.slots
        self.ringing = 0
        self.keep_running = 1  # important for program exit (will be then 0)
        self.thread = threading.Thread(target=self.clock)
        self.thread.start()

    def clock(self):
        while self.keep_running == 1:
            now_time = self.format_time.now_time()
            if now_time in self.alarms:
                del self.alarms[self.alarms.index(now_time)]
                self.save_alarms()
                self.ring()
            time.sleep(3)

    def set(self, slots):
        alarm_time_str = slots['time'][:-10]  # remove the timezone and seconds from time string
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if alarm_time not in self.alarms:
            self.alarms.append(alarm_time)  # add alarm to list
            self.save_alarms()
        if self.format_time.delta_days(alarm_time) >= 0:
            f_time = self.format_time
            return "Der Wecker wird {0} um {1} Uhr {2} klingeln.".format(f_time.future_part(alarm_time),
                                                                         f_time.alarm_hour(alarm_time),
                                                                         f_time.alarm_minute(alarm_time))
        else:  # if date is in the past
            return "Die Zeit liegt in der Vergangenheit. Wecker wurde nicht gestellt."

    def get_on_date(self, slots):
        alarm_date_str = slots['date'][:-16]  # remove the timezone and time from time string
        alarm_date = datetime.datetime.strptime(alarm_date_str, "%Y-%m-%d")
        if self.format_time.delta_days(alarm_date, day_format=1) < 0:
            return "Dieser Tag liegt in der Vergangenheit."
        alarms_on_date = []
        for alarm in self.alarms:
            if alarm_date.date() == alarm.date():
                alarms_on_date.append(alarm)
        if len(alarms_on_date) > 1:
            response = "{0} gibt es {1} Alarme. ".format(self.format_time.future_part(alarms_on_date[0], 1),
                                                         len(alarms_on_date))
            for alarm in alarms_on_date[:-1]:
                response = response + "einen um {0} Uhr {1}, ".format(self.format_time.alarm_hour(alarm),
                                                                      self.format_time.alarm_minute(alarm))
            response = response + "und einen um {0} Uhr {1} .".format(self.format_time.alarm_hour(alarms_on_date[-1]),
                                                                      self.format_time.alarm_minute(alarms_on_date[-1]))
        elif len(alarms_on_date) == 1:
            response = "{0} gibt es einen Alarm um {1} Uhr {2} .".format(
                self.format_time.future_part(alarms_on_date[0], 1),
                self.format_time.alarm_hour(alarms_on_date[0]),
                self.format_time.alarm_minute(alarms_on_date[0]))
        else:
            response = "{0} gibt es keinen Alarm.".format(self.format_time.future_part(alarm_date, day_format=1))
        return response

    def is_alarm(self, slots):
        alarm_time_str = slots['time'][:-10]
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if alarm_time in self.alarms:
            is_alarm = 1
            response = "Ja, {0} wird ein Alarm um {1} Uhr {2} " \
                       "klingeln.".format(self.format_time.future_part(alarm_time, 1),
                                          self.format_time.alarm_hour(alarm_time),
                                          self.format_time.alarm_minute(alarm_time))
        else:
            is_alarm = 0
            response = "Nein, zu dieser Zeit ist kein Alarm gestellt. Möchtest du " \
                       "{0} um {1} Uhr {2} einen Wecker stellen?".format(self.format_time.future_part(alarm_time, 1),
                                                                         self.format_time.alarm_hour(alarm_time),
                                                                         self.format_time.alarm_minute(alarm_time))
            self.slots = slots  # save slots for setting new alarm on confirmation
        return is_alarm, response

    def delete_alarm(self, slots):
        alarm_time_str = slots['time'][:-10]
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if self.format_time.delta_days(alarm_time) < 0:
            return "Diese Zeit liegt in der Vergangenheit."
        if alarm_time in self.alarms:
            self.alarms.remove(alarm_time)
            self.save_alarms()
            return "Der Alarm {0} um {1} Uhr {2} wurde entfernt.".format(self.format_time.future_part(alarm_time, 1),
                                                                         self.format_time.alarm_hour(alarm_time),
                                                                         self.format_time.alarm_minute(alarm_time))
        else:
            return "Dieser Alarm ist nicht vorhanden."

    def delete_date_try(self, slots):
        alarm_date_str = slots['date'][:-16]  # remove the timezone and time from time string
        alarm_date = datetime.datetime.strptime(alarm_date_str, "%Y-%m-%d")
        if self.format_time.delta_days(alarm_date, day_format=1) < 0:
            return "Dieser Tag liegt in der Vergangenheit."
        alarms_on_date = []
        for alarm in self.alarms:
            if alarm_date.date() == alarm.date():
                alarms_on_date.append(alarm)
        if len(alarms_on_date) > 1:
            alarms = True
            response = "{0} gibt es {1} Alarme. Bist du dir sicher?".format(self.format_time.future_part(alarm_date, 1),
                                                                            len(alarms_on_date))
        elif len(alarms_on_date) == 1:
            alarms = True
            response = "{0} gibt es einen Alarm um {1} Uhr {2} . Bist du dir sicher?".format(
                self.format_time.future_part(alarm_date, 1),
                self.format_time.alarm_hour(alarms_on_date[0]),
                self.format_time.alarm_minute(alarms_on_date[0]))
        else:
            alarms = False
            response = "{0} gibt es keinen Alarm.".format(self.format_time.future_part(alarm_date, day_format=1))
        if alarms == 1:
            self.slots = slots
        return alarms, response

    def delete_date(self, slots):
        if slots['answer'] == "yes":
            # date was saved above in global self.slots
            alarm_date_str = self.slots['date'][:-16]  # remove the timezone and time from date string
            alarm_date = datetime.datetime.strptime(alarm_date_str, "%Y-%m-%d")
            for alarm in self.alarms:
                if alarm_date.date() == alarm.date():
                    self.alarms.remove(alarm)
                    self.save_alarms()
            return "Alle Alarme {0} wurden entfernt.".format(self.format_time.future_part(alarm_date, 1))
        else:
            return "Vorgang wurde abgebrochen."

    def delete_all_try(self):
        return len(self.alarms)

    def delete_all(self, slots):
        if slots['answer'] == "yes":
            self.alarms = []
            self.save_alarms()
            return "Es wurden alle Alarme entfernt."
        else:
            return "Vorgang wurde abgebrochen."

    def get_all(self):
        if len(self.alarms) == 0:
            response = "Es gibt keine gestellten Alarme."
        elif len(self.alarms) == 1:
            response = "Es gibt {0} einen Alarm um {1} Uhr {2} .".format(
                self.format_time.future_part(self.alarms[0], 1),
                self.format_time.alarm_hour(self.alarms[0]),
                self.format_time.alarm_minute(self.alarms[0]))
        elif 2 <= len(self.alarms) <= 5:
            response = "Es gibt {0} Alarme in der nächsten Zeit. ".format(len(self.alarms))
            for alarm in self.alarms[:-1]:
                response = response + "einen {0} um {1} Uhr {2}, ".format(self.format_time.future_part(alarm, 1),
                                                                          self.format_time.alarm_hour(alarm),
                                                                          self.format_time.alarm_minute(alarm))
            response = response + "und einen {0} um {1} Uhr {2} .".format(
                self.format_time.future_part(self.alarms[-1], 1),
                self.format_time.alarm_hour(self.alarms[-1]),
                self.format_time.alarm_minute(self.alarms[-1]))
        else:
            response = "Die nächsten sechs Alarme sind ".format(len(self.alarms))
            for alarm in self.alarms[:6]:
                response = response + "einmal {0} um {1} Uhr {2}, ".format(self.format_time.future_part(alarm, 1),
                                                                           self.format_time.alarm_hour(alarm),
                                                                           self.format_time.alarm_minute(alarm))
            response = response + "und {0} um {1} Uhr {2} .".format(self.format_time.future_part(self.alarms[-1], 1),
                                                                    self.format_time.alarm_hour(self.alarms[-1]),
                                                                    self.format_time.alarm_minute(self.alarms[-1]))
        return response

    def ring(self):
        self.player = subprocess.Popen(["omxplayer", "--loop", "--no-osd", "--vol", self.ringing_volume,
                                        self.script_dir + "/resources/timer-sound.mp3"], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.ringing = 1
        self.ringing_timeout = threading.Timer(self.timeout, self.stop)
        self.ringing_timeout.start()

    def stop(self):
        if self.ringing == 1:
            self.ringing = 0
            stdout_data = self.player.communicate(input=b"q")[0]  # send "q" key to omxplayer command
            self.ringing_timeout.cancel()
            return stdout_data

    def save_alarms(self):
        with open(self.saved_alarms_path, "wb") as f:
            pickle.dump(self.alarms, f)

    def read_alarms(self):
        try:
            with open(self.saved_alarms_path, 'rb') as f:
                in_file = pickle.load(f)
                self.format_time = self._FormatTime()  # --------------------------------------------------------------
                now_time = self.format_time.now_time()
            alarms_in_past = []
            for element in in_file:
                delta_seconds = (element - now_time).seconds  # calculate the days between alarm and now
                delta_days = (element - now_time).days
                if delta_days < 0:
                    alarms_in_past.append(element)  # alarm is in past
                else:
                    if delta_seconds == 0:
                        alarms_in_past.append(element)  # alarm shouldn't ring because too short after start
            for element in alarms_in_past:
                in_file.remove(element)
            return in_file
        except EOFError:  # if no list in file
            return []

    class _FormatTime:
        @staticmethod
        def now_time(day_format=0):
            now = datetime.datetime.now()
            if day_format == 0:
                now_time_str = "{0}-{1}-{2} {3}:{4}".format(now.year, now.month, now.day, now.hour, now.minute)
                now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d %H:%M")
            else:
                now_time_str = "{0}-{1}-{2}".format(now.year, now.month, now.day)
                now_time = datetime.datetime.strptime(now_time_str, "%Y-%m-%d")
            return now_time

        def delta_days(self, alarm_time, day_format=0):
            now_time = self.now_time(day_format)
            delta_days = (alarm_time - now_time).days  # calculate the days between alarm and now
            return delta_days

        @staticmethod
        def alarm_hour(alarm_time):
            if alarm_time.hour == 1:  # word correction
                alarm_hour = "ein"
            else:
                alarm_hour = alarm_time.hour
            return alarm_hour

        @staticmethod
        def alarm_minute(alarm_time):
            if alarm_time.minute == 0:  # gap correction in sentence
                alarm_minute = ""
            else:
                alarm_minute = alarm_time.minute
            return alarm_minute

        @staticmethod
        def weekday(alarm_time):
            weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonnstag"]
            # The following must be "alarmtime.isoweekday()" if Sunday is your first day of the week
            alarm_weekday = weekdays[alarm_time.weekday()]  # pick the element from the list
            return alarm_weekday

        def future_part(self, alarm_time, day_format=0):
            now_time = self.now_time()
            delta_days = self.delta_days(alarm_time, day_format=1)
            weekday = self.weekday(alarm_time)
            if delta_days == 0:
                if day_format == 0:
                    delta_seconds = (alarm_time - now_time).seconds
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
                future_part = "am kommenden {0}".format(weekday)
            elif delta_days == 7:
                future_part = "am {0} in genau einer Woche".format(weekday)
            else:
                future_part = "in {0} Tagen, am {1}, dem {2}.{3}.".format(delta_days, weekday,
                                                                          int(alarm_time.day),
                                                                          int(alarm_time.month))
            return future_part
