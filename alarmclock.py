# -*- coding: utf-8 -*-
#                                   Explanations:
import datetime                     # date and time
import time                         # sleep in the clock thread
import threading                    # clock thread in background and alarm timeout
import io                           # opening alarm list file
import os                           # script directory
import subprocess                   # mpg123 command
import pickle                       # saving alarms in list
import paho.mqtt.client as mqtt     # sending mqtt messages
import paho.mqtt.publish as publish
import json                         # payload in mqtt messages


class AlarmClock:
    def __init__(self, config):
        self.script_dir = os.path.abspath(os.path.dirname(__file__))
        self.ringing_volume = config['secret']['ringing_volume']
        self.ringing_timeout = config['secret']['ringing_timeout']
        if not self.ringing_volume:  # if dictionaray not filled with values
            self.ringing_volume = 20
        else:
            self.ringing_volume = int(self.ringing_volume)
        if not self.ringing_timeout:
            self.ringing_timeout = 15
        else:
            self.ringing_timeout = int(self.ringing_timeout)
        self.alarms = []
        self.saved_alarms_path = ".saved_alarms"
        self.format_time = self._FormatTime()
        self.remembered_slots = {}
        self.wanted_intents = []
        self.ringing = 0
        self.clock_thread = threading.Thread(target=self.clock)
        self.clock_thread.start()
        self.player = None
        self.timeout_thread = None
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect("localhost", "1883")
        self.mqtt_client.loop()

    def clock(self):
        while True:
            now_time = self.format_time.now_time()
            if now_time in self.alarms:
                del self.alarms[self.alarms.index(now_time)]
                self.ring()
            time.sleep(3)

    def set(self, slots):
        alarm_time_str = self.format_time.alarm_time_str(slots)  # remove the timezone and else numbers from time string
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if self.format_time.delta_days(alarm_time) >= 0:
            if (alarm_time - self.format_time.now_time()).seconds >= 120:
                if alarm_time not in self.alarms:
                    self.alarms.append(alarm_time)  # add alarm to list
                f_time = self.format_time
                return "Der Wecker wird {0} um {1} Uhr {2} klingeln.".format(f_time.future_part(alarm_time),
                                                                             f_time.alarm_hour(alarm_time),
                                                                             f_time.alarm_minute(alarm_time))
            else:
                return "Dieser Alarm würde jetzt klingeln. Bitte wähle einen anderen Alarm."
        else:  # if date is in the past
            return "Diese Zeit liegt in der Vergangenheit. Wecker wurde nicht gestellt."

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
        alarm_time_str = self.format_time.alarm_time_str(slots)
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
            self.remembered_slots = slots  # save slots for setting new alarm on confirmation
        return is_alarm, response

    def delete_alarm(self, slots):
        alarm_time_str = self.format_time.alarm_time_str(slots)
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if self.format_time.delta_days(alarm_time) < 0:
            return "Diese Zeit liegt in der Vergangenheit."
        if alarm_time in self.alarms:
            self.alarms.remove(alarm_time)
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
        if alarms:
            self.remembered_slots = slots
        return alarms, response

    def delete_date(self, slots):
        if slots['answer'] == "yes":
            # date was saved above in global self.slots
            alarm_date_str = self.remembered_slots['date'][:-16]  # remove the timezone and time from date string
            alarm_date = datetime.datetime.strptime(alarm_date_str, "%Y-%m-%d")
            for alarm in self.alarms:
                if alarm_date.date() == alarm.date():
                    self.alarms.remove(alarm)
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
        sound_file = self.script_dir + "/alarm-sound.wav"
        # 0-100 --> 0-30000  (source: https://sourceforge.net/p/mpg123/feature-requests/35/)
        calc_volume = abs(self.ringing_volume) * 300
        # very important (execute where Snips is running on, e.g. on a Raspi): "sudo usermod -a -G audio _snips-skills"
        #self.player = subprocess.Popen(["mpg123", "--quiet", "--loop", "-1", "-C", "-f", str(calc_volume), sound_file])
        #self.mqtt_client.publish('hermes/external/alarmclock/ringing', json.dumps({"text": "test"}))

        wav_file = open(sound_file, 'rb')
        audio_wav = wav_file.read()
        wav_file.close()
        #self.mqtt_client.publish('hermes/audioServer/default/playBytes/blablub', payload=audio_wav)
        publish.single('hermes/audioServer/default/playBytes/blablub', payload=audio_wav, hostname="localhost", port=1883)
        print("Ringing...")
        self.ringing = 1
        self.timeout_thread = threading.Timer(self.ringing_timeout, self.stop)
        self.timeout_thread.start()

    def stop(self):
        if self.ringing == 1:
            self.ringing = 0
            #self.player.terminate()
            self.timeout_thread.cancel()

    def save_alarms(self):
        with io.open(self.saved_alarms_path, "wb") as f:
            pickle.dump(self.alarms, f)

    class _FormatTime:
        def __init__(self):
            pass

        @staticmethod
        def alarm_time_str(slots):
            # example string: "2015-04-08 09:39:00 +02:00"
            return "{}:{}".format(slots['time'].split(":")[0], slots['time'].split(":")[1])

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
