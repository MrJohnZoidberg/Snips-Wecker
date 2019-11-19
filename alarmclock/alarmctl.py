import json
import datetime
import threading
import time
import uuid
from . import formattime as ftime
from . import utils
from .site import Site
from .alarm import Alarm


class AlarmControl:
    def __init__(self, config, mqtt_client):
        self.config = config
        self.saved_alarms_path = ".saved_alarms.json"
        self.sites_dict = {}
        for room, siteid in config['dict_siteids'].items():
            ringing_timeout = self.config['ringing_timeout'][siteid]
            ringing_volume = self.config['ringing_volume'][siteid]
            ringtone_wav = utils.edit_volume("alarm-sound.wav", ringing_volume)
            self.sites_dict[siteid] = Site(siteid, room, ringing_timeout, ringtone_wav)
        self.alarms = self.restore()
        self.save()
        self.clock_thread = threading.Thread(target=self.clock)
        self.clock_thread.start()
        self.mqtt_client = mqtt_client
        self.mqtt_client.message_callback_add('hermes/hotword/#', self.on_message_hotword)

    def clock(self):
        """
        Checks in a loop if the current time and date matches with one of the alarm dictionary.
        :return: Nothing
        """
        while True:
            now_time = ftime.get_now_time()

            for alarm in self.get_alarms():
                if not alarm.sun_rising and now_time + datetime.timedelta(minutes=30) >= alarm.datetime:
                    minutes_until_alarm = int((alarm.datetime - now_time).total_seconds() // 60)
                    payload = {'minutes': minutes_until_alarm, 'room': alarm.site.room}
                    self.mqtt_client.publish('homeassistant/sunriseStart', json.dumps(payload))
                    alarm.sun_rising = True
                if now_time == alarm.datetime:
                    self.start_ringing(alarm)
            time.sleep(5)

    def start_ringing(self, alarm):
        site = alarm.site
        site.ringing_alarm = alarm
        site.timeout_thread = threading.Timer(site.ringing_timeout, self.timeout_reached, args=(site,))
        site.timeout_thread.start()
        self.mqtt_client.message_callback_add('hermes/audioServer/{siteId}/playFinished'.format(
            siteId=site.siteid), self.on_message_playfinished)
        self.ring(site)

    def ring(self, site):
        """
        Publishes the ringtone wav over MQTT to the soundserver and generates a random UUID for it.
        :param site: The site object (site of the user)
        :return: Nothing
        """
        site.ringtone_id = str(uuid.uuid4())
        self.mqtt_client.publish('hermes/audioServer/{site_id}/playBytes/{ring_id}'.format(
            site_id=site.siteid, ring_id=site.ringtone_id), payload=site.ringtone_wav)

    def stop_ringing(self, site):
        """
        Sets self.ringing_dict[siteId] to False so on_message_playfinished won't start a new ring.
        :param site: The site object (site of the user)
        :return: Nothing
        """
        site.ringing_alarm = None
        site.ringtone_id = None
        site.timeout_thread.cancel()  # cancel timeout thread from siteId
        site.timeout_thread = None
        self.mqtt_client.message_callback_remove(
            'hermes/audioServer/{site_id}/playFinished'.format(site_id=site.siteid)
        )

    def timeout_reached(self, site):
        site.ringing_alarm.missed = True
        self.stop_ringing(site)

    def on_message_playfinished(self, *args):
        """
        Called when ringtone was played on specific site. If alarm on site still active, the
        ringtone is played again.
        :param args: MQTT objects (from paho)
        :return: Nothing
        """
        data = json.loads(args[2].payload.decode())
        site = self.sites_dict[data['siteId']]
        if site.ringing_alarm and site.ringtone_id == data['id']:
            self.ring(site)

    def on_message_hotword(self, *args):
        """
        Called when hotword is recognized while alarm is ringing. If siteId matches the one of the
        current ringing alarm, it is stopped.
        :param args: MQTT objects (from paho)
        :return: Nothing
        """
        data = json.loads(args[2].payload.decode())
        site = self.sites_dict.get(data['siteId'])
        if site and site.ringing_alarm:
            self.stop_ringing(site)
            site.session_active = True
            self.mqtt_client.message_callback_add(
                'hermes/dialogueManager/sessionStarted', self.on_message_sessionstarted
            )

    def on_message_sessionstarted(self, *args):
        """
        Called when Snips started a new session. Publishes a message to end this immediately and Snips
        will notify the user that the alarm has ended.
        :param args: MQTT objects (from paho)
        :return: Nothing
        """
        data = json.loads(args[2].payload.decode())
        site = self.sites_dict.get(data['siteId'])
        if not site or not site.session_active:
            return

        site.session_active = False
        self.mqtt_client.message_callback_remove('hermes/dialogueManager/sessionStarted')
        # Stop ASR listening before session end; fix for error in Snips service
        self.mqtt_client.publish('hermes/asr/stopListening', json.dumps(
            {'siteId': data['siteId'], 'sessionId': data['sessionId']}
        ))
        now_time = datetime.datetime.now()
        text = "Alarm beendet. Es ist jetzt {h} Uhr {min} .".format(
            h=ftime.get_alarm_hour(now_time),
            min=ftime.get_alarm_minute(now_time)
        )
        self.mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps(
            {"text": text, "sessionId": data['sessionId']}
        ))

    def add(self, alarmobj):
        if alarmobj not in self.alarms:
            self.alarms.append(alarmobj)
        self.save()

    def save(self):
        with open(self.saved_alarms_path, "w") as f:
            f.write(json.dumps(self.get_unpacked_objects_list()))

    def restore(self):
        with open(self.saved_alarms_path, "r") as f:
            alarms = list()
            try:
                alarms_list = json.load(f)
                for alarm_dict in alarms_list:
                    if alarm_dict['siteid'] in self.sites_dict:
                        alarm = Alarm(self.sites_dict[alarm_dict['siteid']])
                        alarm.datetime_str(alarm_dict['datetime'])
                        alarms.append(alarm)
            except (ValueError, TypeError):
                pass
        return alarms

    def get_unpacked_objects_list(self):
        alarms_list = []
        for alarm in self.alarms:
            alarms_list.append(alarm.data_dict)
        return alarms_list

    def get_alarms(self, dtobject=None, siteid=None, only_ringing=False):
        if only_ringing:
            filtered_alarms = [alarm for alarm in self.alarms if alarm.ringing]
        else:
            filtered_alarms = [alarm for alarm in self.alarms if not alarm.passed]
        if dtobject:
            filtered_alarms = [alarm for alarm in filtered_alarms
                               if alarm.datetime == dtobject and not alarm.passed]
        if siteid:
            filtered_alarms = [alarm for alarm in filtered_alarms
                               if alarm.site.siteid == siteid and not alarm.passed]
        return filtered_alarms

    def get_missed_alarms(self, dtobject=None, siteid=None):
        filtered_alarms = [alarm for alarm in self.alarms if alarm.passed]
        if dtobject:
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime == dtobject]
        if siteid:
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.site.siteid == siteid]
        return filtered_alarms

    def delete_multi(self, alarms):
        for alarm in alarms:
            if alarm.site.sun_rising_alarm == alarm:
                alarm.site.sun_rising_alarm = None
            self.alarms.remove(alarm)
        self.save()
