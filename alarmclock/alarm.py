import io
import json
from datetime import datetime as dt
from . import formattime as ftime
import threading
import time
import uuid
import functools # functools.partial for threading.Timeout callback with parameter
from . import utils
from . translation import Translation


class Site:
    
    def __init__(self, siteid, room, ringtone_status, ringing_timeout, ringtone_wav):
        self.siteid = siteid
        self.room = room
        self.ringing_timeout = ringing_timeout
        self.ringtone_status = ringtone_status
        self.ringtone_wav = ringtone_wav
        self.ringing_alarm = None
        self.ringtone_id = None
        self.timeout_thread = None
        self.session_pending = False


class Alarm:
    
    FORMAT = "%Y-%m-%d %H:%M"
    
    def __init__(self, datetime=None, site=None, repetition=None, **kwargs):
        if type( datetime) is str:
            self.datetime = dt.strptime( datetime, self.FORMAT)
        else:
            self.datetime = datetime
        self.repetition = repetition
        self.site = site
        self.passed = False

    def get_data_dict(self):
        return {
            'datetime': dt.strftime( self.datetime, self.FORMAT),
            'siteid': self.site.siteid,
            'room': self.site.room,
            'repetition': self.repetition
        }

    def missed( self):
        return (self.datetime - dt.now()).days < 0


class AlarmControl:
    
    def __init__(self, config, language, mqtt_client, temp_memory):
        self.config = config
        self.saved_alarms_path = ".saved_alarms.json"
        self.sites_dict = {}
        for room, siteid in config['dict_siteids'].items():
            ringtone_status = self.config['ringtone_status'][siteid]
            ringing_timeout = self.config['ringing_timeout'][siteid]
            ringing_volume = self.config['ringing_volume'][siteid]
            ringtone_wav = utils.edit_volume("alarm-sound.wav", ringing_volume)
            self.sites_dict[siteid] = Site(siteid, room, ringtone_status, ringing_timeout, ringtone_wav)
        if config['restore_alarms']:
            self.alarms = self.restore()
        else:
            self.alarms = []
            self.save()
        self.clock_thread = threading.Thread( target=self.clock)
        self.clock_thread.start()
        self.translation = Translation(language)
        self.temp_memory = temp_memory
        self.mqtt_client = mqtt_client
        self.mqtt_client.message_callback_add('hermes/hotword/#', self.on_message_hotword)
        # TODO: Publish other messages over mqtt
        self.mqtt_client.message_callback_add('external/alarmclock/stopRinging', self.on_message_stopringing)
        self.mqtt_client.subscribe([('external/alarmclock/#', 0), ('hermes/dialogueManager/#', 0),
                                    ('hermes/hotword/#', 0), ('hermes/audioServer/#', 0)])

    def clock(self):

        """
        Checks in a loop if the current time and date matches with one of the alarm dictionary.
        :return: Nothing
        """

        while True:
            now_time = ftime.get_now_time()
            for alarm in self.get_alarms( now_time):
                if alarm.passed: continue
                alarm.passed = True
                self.mqtt_client.publish('external/alarmclock/ringingStarted',
                    json.dumps(alarm.get_data_dict()))
                self.start_ringing(alarm, now_time)
            time.sleep(1)


    def start_ringing(self, alarm, now_time):
        site = alarm.site
        if site.ringtone_status:
            self.temp_memory[site.siteid] = {'alarm': now_time}
            self.mqtt_client.message_callback_add('hermes/audioServer/{siteId}/playFinished'.format(
                siteId=site.siteid), self.on_message_playfinished)
            self.ring(site)
            site.ringing_alarm = alarm
            site.timeout_thread = threading.Timer(site.ringing_timeout,
                                                  functools.partial(self.stop_ringing, site))
            site.timeout_thread.start()
        else:
            self.mqtt_client.publish('external/alarmclock/ringingStopped',
                json.dumps(alarm.get_data_dict()))


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

        self.mqtt_client.publish('external/alarmclock/ringingStopped',
                                 json.dumps(site.ringing_alarm.get_data_dict()))
        # TODO: delete alarm after captcha or snooze or sth
        site.ringing_alarm = None
        site.ringtone_id = None
        site.timeout_thread.cancel()  # cancel timeout thread from siteId
        site.timeout_thread = None
        self.mqtt_client.message_callback_remove('hermes/audioServer/{site_id}/playFinished'.format(
            site_id=site.siteid))

    def on_message_playfinished(self, client, userdata, msg):

        """
        Called when ringtone was played on specific site. If self.ringing_dict[siteId] is True, the
        ringtone is played again.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        site = self.sites_dict[json.loads(msg.payload.decode("utf-8"))['siteId']]
        if site.ringing_alarm and site.ringtone_id == json.loads(msg.payload.decode("utf-8"))['id']:
            self.ring(site)

    def on_message_hotword(self, client, userdata, msg):

        """
        Called when hotword is recognized while alarm is ringing. If siteId matches the one of the
        current ringing alarm, it is stopped.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        site = self.sites_dict[json.loads(msg.payload.decode("utf-8"))['siteId']]
        if site.ringing_alarm:
            self.stop_ringing(site)
            site.session_pending = True  # TODO
            self.mqtt_client.message_callback_add('hermes/dialogueManager/sessionStarted',
                                                  self.on_message_sessionstarted)

    def on_message_stopringing(self, client, userdata, msg):

        """
        Called when message 'external/alarmclock/stopRinging' was received via MQTT.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        site = self.sites_dict[json.loads(msg.payload.decode("utf-8"))['siteId']]
        if site.ringing_alarm:
            self.stop_ringing(site)

    def on_message_sessionstarted(self, client, userdata, msg):

        """
        Called when Snips started a new session. Publishes a message to end this immediately and Snips
        will notify the user that the alarm has ended.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """
        data = json.loads(msg.payload.decode("utf-8"))
        # self.mqtt_client.publish('hermes/asr/toggleOn')
        if not self.config['snooze_config']['state'] and self.sites_dict[data['siteId']].session_pending:
            self.sites_dict[data['siteId']].session_pending = False
            self.mqtt_client.message_callback_remove('hermes/dialogueManager/sessionStarted')
            now_time = dt.now()
            text = self.translation.get("Alarm is now ended.") + " " + self.translation.get("It's {h}:{min} .", {
                'h': ftime.get_alarm_hour(now_time), 'min': ftime.get_alarm_minute(now_time)})
            self.mqtt_client.publish('hermes/dialogueManager/endSession',
                                     json.dumps({"text": text, "sessionId": data['sessionId']}))

        elif self.config['snooze_config']['state'] and self.sites_dict[data['siteId']].session_pending:
            self.sites_dict[data['siteId']].session_pending = False
            self.mqtt_client.message_callback_remove('hermes/dialogueManager/sessionStarted')
            self.mqtt_client.publish('hermes/dialogueManager/endSession',
                                     json.dumps({"sessionId": data['sessionId']}))
            self.mqtt_client.publish('hermes/dialogueManager/startSession',
                                     json.dumps({'siteId': data['siteId'],
                                                 'init': {'type': "action", 'text': "Was soll der Alarm tun?",
                                                          'canBeEnqueued': True,
                                                          'intentFilter': ["domi:answerAlarm"]}}))

    def add(self, alarmobj):
        if alarmobj not in self.alarms:
            self.alarms.append(alarmobj)
        self.save()

    def save(self):
        with io.open( self.saved_alarms_path, "w") as f:
            f.write( json.dumps( [ alarm.get_data_dict() for alarm in self.alarms ]))

    def restore(self):
        with io.open(self.saved_alarms_path, "r") as f:
            return [ Alarm( **alarm_dict) for alarm_dict in json.load( f) ]

    def get_alarms(self, dtobject=None, siteid=None):
        filtered_alarms = [alarm for alarm in self.alarms if not alarm.missed()]
            
        if dtobject:
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime == dtobject]
        if siteid:
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.site.siteid == siteid]
        return filtered_alarms

    def get_missed_alarms(self, dtobject=None, siteid=None):
        filtered_alarms = [alarm for alarm in self.alarms if alarm.missed()]
        
        if dtobject:
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.datetime == dtobject]
        if siteid:
            filtered_alarms = [alarm for alarm in filtered_alarms if alarm.site.siteid == siteid]
        return filtered_alarms

    def delete_alarms(self, alarms):
        for alarm in alarms:
            self.alarms.remove(alarm)
        self.save()
