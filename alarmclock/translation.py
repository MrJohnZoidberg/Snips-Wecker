# -*- coding: utf-8 -*-

TRANSLATIONS_DE = {

    "Done.":
        "Erledigt.",
    "This room here hasn't been configured yet.":
        "Dieser Raum wurde noch nicht eingestellt.",
    "The room {room} has not been configured yet.":
        "Der Raum {room} wurde noch nicht eingestellt.",
    "as of":
        "ab",
    "from":
        "von",
    "to {future_part_to} {h_to}:{min_to}":
        "bis {future_part_to} {h_to} Uhr {min_to}",
    "{from_word} {future_part_from} {h_from}:{min_from}":
        "{from_word} {future_part_from} {h_from} Uhr {min_from}",
    "at {h}:{min}":
        "um {h} Uhr {min}",
    "This alarm would ring now.":
        "Dieser Alarm würde jetzt klingeln.",
    "The alarm will ring {room_part} {future_part} at {h}:{min} .":
        "Der Wecker wird {future_part} um {h} Uhr {min} {room_part} klingeln.",
    "The next five are: ":
        "Die nächsten fünf sind: ",
    "{num} alarms":
        "{num} Alarme",
    "There is {room_part} {future_part} {time_part} {num_part}{end}":
        "Es gibt {room_part} {future_part} {time_part} {num_part}{end}",
    "There are {room_part} {future_part} {time_part} {num_part}{end}":
        "Es gibt {room_part} {future_part} {time_part} {num_part}{end}",
    "{future_part} {time_part} {room_part}":
        "{future_part} {time_part} {room_part}",
    "The {only_part} alarm {future_part} {time_part} {room_part} has been deleted.":
        "Der {only_part} Alarm {future_part} {time_part} {room_part} wurde gelöscht.",
    "Alarm is now ended.":
        "Alarm beendet.",
    "It's {h}:{min} .":
        "Es ist jetzt {h} Uhr {min} .",
    "There are {future_part} {time_part} {room_part} {num} alarms. Are you sure?":
        "Es gibt {future_part} {time_part} {room_part} {num} Alarme. Bist du dir sicher?",
    "There is no alarm {room_part} {future_part} {time_part}.":
        "Es gibt {room_part} {future_part} {time_part} keinen Alarm.",
    "You missed {room_part} {future_part} {time_part} {num_part}{end}":
        "Du hast {room_part} {future_part} {time_part} {num_part} verpasst{end}",
    "This time is in the past.":
        "Diese Zeit liegt in der Vergangenheit.",
    "Please set another alarm.":
        "Bitte stelle einen anderen Alarm.",
    "I'm afraid I didn't understand you.":
        "Ich habe dich leider nicht verstanden.",
    "Please see the instructions for this alarm clock app for how to add rooms.":
        "Bitte schaue in der Anleitung von dieser Wecker-Äpp nach, wie man Räume hinzufügen kann.",
    "here":
        "hier",
    "no alarm":
        "keinen Alarm",
    "one alarm":
        "einen Alarm",
    "and":
        "und",
    "monday":
        "Montag",
    "tuesday":
        "Dienstag",
    "wednesday":
        "Mittwoch",
    "thursday":
        "Donnerstag",
    "friday":
        "Freitag",
    "saturday":
        "Samstag",
    "sunday":
        "Sonntag",
    "today":
        "heute",
    "tomorrow":
        "morgen",
    "the day after tomorrow":
        "übermorgen",
    "one hour":
        "einer Stunde",
    "{delta_hours} hours":
        "{delta_hours} Stunden",
    "one minute":
        "einer Minute",
    "{delta_minutes} minutes":
        "{delta_minutes} Minuten",
    "in {hour_part}":
        "in {hour_part}",
    "in {hour_part} and {minute_part}":
        "in {hour_part} und {minute_part}",
    "in {minute_part}":
        "in {minute_part}",
    "in {delta_days} days, on {weekday}, the {day}.{month}.":
        "in {delta_days} Tagen, am {weekday}, dem {day}.{month}.",
    "on {weekday}":
        "am {weekday}",
    "on {weekday} in exactly one week":
        "am {weekday} in genau einer Woche",
    "only":
        "einzige",
    "Repeat the following sentence.":
        "Wiederhole den folgenden Satz."
}


PREPOSITIONS = {
    "de-DE": {
        "default":          "",
        "Sauna":            "in der",
        "Draußen":          "",
        "Wartezimmer":      "im",
        "Eingang":          "im",
        "Gang":             "im",
        "Toilette":         "in der",
        "Abstellkammer":    "in der",
        "Spielzimmer":      "im",
        "Garage":           "in der",
        "Garten":           "im",
        "Atrium":           "im",
        "Foyer":            "im",
        "Vestibül":         "im",
        "Büro":             "im",
        "Atelier":          "im",
        "Wintergarten":     "im",
        "Waschküche":       "in der",
        "Galerie":          "in der",
        "Aula":             "in der",
        "Dachboden":        "auf dem",
        "Leitstand":        "im",
        "Cella":            "in der",
        "Kommandozentrale": "in der",
        "Konferenzraum":    "im",
        "Kesselhaus":       "im",
        "Speisekammer":     "in der",
        "Umkleideraum":     "im",
        "Esszimmer":        "im",
        "Monteurzimmer":    "im",
        "Wartehalle":       "in der",
        "Keller":           "im",
        "Küche":            "in der",
        "Arbeitszimmer":    "im",
        "Badezimmer":       "im",
        "Kinderzimmer":     "im",
        "Wohnzimmer":       "im",
        "Schlafzimmer":     "im",
        "Balkon":           "auf dem"
    },
    "fr-FR": {
        "default":          ""
    },
    "en-US": {
        "default":          "in the"
    }
}


class Translation:
    def __init__(self, language):
        self.language = language

    def get(self, description, data=None):
        if not data:
            data = {}
        if self.language == "de-DE":
            return TRANSLATIONS_DE[description].format(**data)
        elif self.language == "en-US":
            return description.format(**data)

    def get_prepos(self, room):
        if self.language not in PREPOSITIONS.keys():
            return ""
        if room in PREPOSITIONS[self.language].keys():
            preposition = PREPOSITIONS[self.language][room]
        elif "default" in PREPOSITIONS[self.language].keys():
            preposition = PREPOSITIONS[self.language]["default"]
        else:
            preposition = ""
        return preposition
