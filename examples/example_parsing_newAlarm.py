import json
import datetime
import paho.mqtt.client as mqtt


def on_connect(client, userdata, flags, rc):
    mqttc.subscribe('external/alarmclock/out/newAlarm')


def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    dt = datetime.datetime
    # parsing of string to datetime object
    dt_newalarm = dt.strptime(data['new']['datetime'], "%Y-%m-%d %H:%M")
    # dictionary with all alarms
    alarms_dict = {dt.strptime(dtstr, "%Y-%m-%d %H:%M"): data['all'][dtstr] for dtstr in data['all']}
    # [...]


mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect(host='localhost', port=1883)
mqttc.loop_forever()
