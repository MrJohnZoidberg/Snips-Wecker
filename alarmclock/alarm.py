import io
import json
from datetime import datetime as dt
import threading
import time
import functools
from . import utils
from . translation import _, spoken_time


class Site:
    
    def __init__( self, siteid, room, ringtone_status, ringing_timeout, ringtone_wav):
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
    
    def __init__( self, datetime=None, site=None, repetition=None, **kwargs):
        if type( datetime) is str:
            self.datetime = dt.strptime( datetime, self.FORMAT)
        else:
            self.datetime = datetime
        self.repetition = repetition
        self.site = site
        self.passed = False


    def get_data_dict( self):
        return {
            'datetime': dt.strftime( self.datetime, self.FORMAT),
            'siteid': self.site.siteid,
            'room': self.site.room,
            'repetition': self.repetition
        }


    def missed( self):
        return ( self.datetime - dt.now()).days < 0


class AlarmControl:
    
    def __init__( self, config, mqtt_client):
        self.config = config
        self.mqtt_client = mqtt_client
        self.temp_memory = {}
        self.alarms = []        
        self.saved_alarms_path = ".saved_alarms.json"
        
        if config['restore_alarms']: self.alarms = self.restore()
        else: self.save()
            
        self.sites_dict = { siteid : Site( siteid, room, 
                self.config['ringtone_status'][siteid],
                self.config['ringing_timeout'][siteid],
                utils.edit_volume("alarm-sound.wav", self.config['ringing_volume'][siteid]))
            for room, siteid in config['dict_siteids'].items() }
            
        self.clock_thread = threading.Thread( target=self.clock)
        self.clock_thread.start()
        
        self.mqtt_client.subscribe([('hermes/audioServer/+/playFinished', 0)])
        self.mqtt_client.topic( 'hermes/hotword/+/detected', qos=1, json=True)( self.on_message_hotword)
        self.mqtt_client.on_session_ended( self.on_message_session_ended)


    def clock( self):
        """
        Checks in a loop if the current time and date matches with one of the alarm dictionary.
        :return: Nothing
        """

        while True:
            now = dt.now()
            now_time = dt( now.year, now.month, now.day, now.hour, now.minute)
            for alarm in self.get_alarms( now_time):
                print( alarm)
                if alarm.passed: continue
                alarm.passed = True
                self.start_ringing(alarm, now_time)
            time.sleep(1)


    def start_ringing( self, alarm, now_time):
        site = alarm.site
        if site.ringtone_status:
            self.temp_memory[site.siteid] = now_time
            self.mqtt_client.message_callback_add(
                'hermes/audioServer/%s/playFinished' % site.siteid,
                self.on_message_playfinished)
            self.mqtt_client.play_sound( site.siteid, site.ringtone_wav)
            site.ringing_alarm = alarm
            site.timeout_thread = threading.Timer(
                site.ringing_timeout, functools.partial( self.stop_ringing, site))
            site.timeout_thread.start()


    def stop_ringing( self, site):
        """
        Sets self.ringing_dict[siteId] to False so on_message_playfinished won't start a new ring.
        :param site: The site object (site of the user)
        :return: Nothing
        """

        site.ringing_alarm = None
        site.ringtone_id = None
        site.timeout_thread.cancel()  # cancel timeout thread from siteId
        site.timeout_thread = None
        self.mqtt_client.message_callback_remove('hermes/audioServer/%s/playFinished' % site.siteid)


    def on_message_playfinished( self, client, userdata, msg):

        """
        Called when ringtone was played on specific site. If self.ringing_dict[siteId] is True, the
        ringtone is played again.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """
        
        payload = json.loads(msg.payload.decode())
        site = self.sites_dict[payload['siteId']]
        if site.ringing_alarm and site.ringtone_id == payload['id']:
            # Play it again, Sam
            self.mqtt_client.play_sound( site.siteid, site.ringtone_wav)


    def on_message_hotword( self, client, userdata, msg):

        """
        Called when hotword is recognized while alarm is ringing. If siteId matches the one of the
        current ringing alarm, it is stopped.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """

        payload = json.loads(msg.payload.decode())
        site = self.sites_dict[payload['siteId']]
        if site.ringing_alarm:
            self.stop_ringing(site)
            site.session_pending = True  # TODO
            self.mqtt_client.message_callback_add(
                self.mqtt_client.SESSION_STARTED, self.on_message_session_started)


    def on_message_session_started( self, client, userdata, msg):

        """
        Called when Snips started a new session. Publishes a message to end this immediately and Snips
        will notify the user that the alarm has ended.
        :param client: MQTT client object (from paho)
        :param userdata: MQTT userdata (from paho)
        :param msg: MQTT message object (from paho)
        :return: Nothing
        """
        
        payload = json.loads( msg.payload.decode())
        site = self.sites_dict[ payload['siteId']]
        if not site.session_pending: return

        site.session_pending = False
        self.mqtt_client.message_callback_remove( self.mqtt_client.SESSION_STARTED)

        if self.config['snooze_config']['state']:
            self.mqtt_client.end_session( sessionId=payload['sessionId'])
            self.mqtt_client.start_session( payload['siteId'],
                self.mqtt_client.action_init( intentFilter=["domi:answerAlarm"],
                    text=_("What should the alarm do?")))

        else:
            self.mqtt_client.end_session( session_id=payload['sessionId'],
                text=_("Alarm is now ended. It is {time} .").format(
                    time=spoken_time( dt.now())))


    def on_message_session_ended( self, client, userdata, msg):
        if self.temp_memory.get( msg.payload['siteId']) \
        and msg.payload['termination']['reason'] != "nominal":
            # if session was ended while confirmation process clean the past intent memory
            del self.temp_memory[ msg.payload['siteId']]


    def add( self, alarmobj):
        if alarmobj not in self.alarms:
            self.alarms.append(alarmobj)
            self.save()


    def save( self):
        with io.open( self.saved_alarms_path, "w") as f:
            f.write( json.dumps( [ alarm.get_data_dict() for alarm in self.alarms ]))


    def restore( self):
        with io.open( self.saved_alarms_path, "r") as f:
            return [ Alarm( **alarm_dict) for alarm_dict in json.load( f) ]


    def get_alarms( self, dtobject=None, siteid=None):
        alarms = filter( lambda a: a.missed(), self.alarms)
        if dtobject: alarms = filter( lambda a: a.datetime == dtobject, alarms)
        if siteid:   alarms = filter( lambda a: a.site.siteid == siteid, alarms)
        return alarms


    def get_missed_alarms( self, dtobject=None, siteid=None):
        alarms = filter( lambda a: a.missed(), self.alarms)
        if dtobject: alarms = filter( lambda a: a.datetime == dtobject, alarms)
        if siteid:   alarms = filter( lambda a: a.site.siteid == siteid, alarms)
        return alarms


    def delete_alarms( self, alarms):
        if alarms:
            for alarm in alarms: self.alarms.remove( alarm)
            self.save()
