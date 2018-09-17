# -*- coding: utf-8 -*-

TRANSLATION_DE = {

    "done": "Erledigt.",

    "this room not configured":
        "Dieser Raum wurde noch nicht eingestellt. Bitte schaue in der Anleitung von dieser Wecker-Äpp "
        "nach, wie man Räume hinzufügen kann.",

    "room not configured":
        "Der Raum {room} wurde noch nicht eingestellt. Bitte schaue in der Anleitung von dieser Wecker-Äpp "
        "nach, wie man Räume hinzufügen kann.",

    "here":
        "hier",

    "not understood":
        "Ich habe dich leider nicht verstanden.",

    "time in past":
        "Diese Zeit liegt in der Vergangenheit. Bitte stelle einen anderen Alarm.",

    "alarm would ring now":
        "Dieser Alarm würde jetzt klingeln. Bitte stelle einen anderen Alarm.",

    "alarm will ring":
        "Der Wecker wird {future_part} um {h} Uhr {min} {room_part} klingeln.",

    "next five are":
        "Die nächsten fünf sind: ",

    "no alarm":
        "keinen Alarm",

    "one alarm":
        "einen Alarm",

    "multiple alarms":
        "{num} Alarme",

    "there is alarm":
        "Es gibt {room_part} {future_part} {num_part}{end}",

    "there are alarms":
        "Es gibt {room_part} {future_part} {num_part}{end}",

    "individual alarms":
        "{future_part} um {h} Uhr {min} {room_part}",

    "and":
        "und",

    "single alarm deleted":
        "Der Alarm {future_part} {room_part} wurde gelöscht.",

    "alarm ended and clock":
        "Alarm beendet. Es ist jetzt {h} Uhr {min} .",

    "ask for deletion":
        "Es gibt {future_part} {room_part} {num} Alarme. Bist du dir sicher?",

    "there is no alarm":
        "Es gibt {room_part} {future_part} keinen Alarm."
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
            return TRANSLATION_DE[description].format(**data)

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
