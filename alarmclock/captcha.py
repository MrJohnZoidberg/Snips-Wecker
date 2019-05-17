# -*- coding: utf-8 -*-

import random
import formattime as ftime
import datetime
from translation import Translation


class Captcha:
    def __init__(self, language, captcha_type, captcha_difficulty=1):
        self.translation = Translation(language)
        self.captcha_type = captcha_type
        self.captcha_difficulty = captcha_difficulty

    def new_captcha(self, dtobj=None):
        if self.captcha_type == "math":
            operator = random.choice(["+", "-"])
            if operator == "-" and self.captcha_difficulty == 1:
                while True:
                    first = random.randrange(1, 20)
                    second = random.randrange(1, 20)
                    if first > second:
                        break
            elif self.captcha_difficulty == 1:
                first = random.randrange(1, 20)
                second = random.randrange(1, 20)
            elif self.captcha_difficulty == 2:
                first = random.randrange(11, 20)
                second = random.randrange(11, 20)
            elif self.captcha_difficulty == 3:
                while True:
                    first = random.randrange(21, 60)
                    second = random.randrange(21, 60)
                    if abs(eval(str(first) + operator + str(second))) > 20:
                        break
            else:
                first = random.randrange(1, 10)
                second = random.randrange(1, 10)
            term = "{first} {operator} {second}".format(first=first, operator=operator, second=second)
            solution = str(eval(term))
            excercise = "Was ist {term} ?".format(term=term)
            return excercise, solution
        elif self.captcha_type == "clock":
            now_time = datetime.datetime.now()
            hours = ftime.get_alarm_hour(now_time)
            minutes = ftime.get_alarm_minute(now_time)
            solution = (hours, minutes)
            clock_part = self.translation.get("It's {h}:{min} .", {'h': hours, 'min': minutes})
            excercise = self.translation.get("Repeat the following sentence.") + " " + clock_part
            return excercise, solution


if __name__ == "__main__":
    captcha = Captcha("en-US", "clock")
    print(captcha.new_captcha())
