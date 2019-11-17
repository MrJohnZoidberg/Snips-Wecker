class Site:
    def __init__(self, siteid, room, ringing_timeout, ringtone_wav):
        self.siteid = siteid
        self.room = room
        self.ringing_timeout = ringing_timeout
        self.ringtone_wav = ringtone_wav
        self.ringing_alarm = None
        self.ringtone_id = None
        self.timeout_thread = None
        self.session_active = False
