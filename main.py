#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from random import randint, choice, shuffle
from time import time
import telebot


TELEBOT_TOKEN = '1075640775:AAEc3l9jrnaMtTOdi41Wv58hndDSwSXhExA'
TeleBot = telebot.TeleBot(TELEBOT_TOKEN)
ADMIN_ID = [150486866]

USERS = {}
ROOMS = {}
EVENTS = set()


class Event:
    def __init__(self, init_time, length, target, message):
        self.init_time = init_time
        self.end_time = init_time + length
        self.target = target
        self.message = message

    def check(self, cur_time):
        if cur_time > self.end_time:
            self.target.send_msg(self.message)
            return True
        else:
            return False


class Room:
    def __init__(self, room_id):
        self.id = room_id
        self.dict = []
        self.guessed = []
        self.users = []

        self.round_time = 20
        self.bonus_time = 2
        self.offset_time = 0.2

        self.last_round_time = 0.0
        self.cur_player = None

    def add_word(self, word):
        self.dict.append(word)

    def get_word(self, player):
        if not self.dict:
            return 'Слова закончились'
        if self.cur_player is not player:
            return 'Сейчас не ваш раунд'

        shuffle(self.dict)
        word = self.dict[-1]
        self.dict.pop()
        return word

    def guess_word(self, word):
        if word in self.dict:
            del self.dict[self.dict.index(word)]
        self.guessed.append(word)

    def add_player(self, player):
        self.users.append(player)

    def reset(self):
        self.dict = self.dict + self.guessed
        self.guessed = []

    def start_round(self, player):
        t = time()
        if t - self.last_round_time < self.round_time + self.bonus_time:
            return 'Сейчас идет раунд другого игрока'

        if not self.dict:
            return 'Слова закончились! Жми /reset, чтобы начать ту же шляпу заново'

        self.send_msg(player.name + ' начал раунд')
        t = time()
        self.last_round_time = time
        self.cur_player = player
        EVENTS.add(Event(t, self.round_time - self.offset_time, self, player.name + ' уже не может обьяснять'))
        EVENTS.add(Event(t, self.round_time + self.bonus_time - self.offset_time, self, player.name + ' закончил раунд'))
        
        word = self.get_word(player)
        return word

    def send_msg(self, message):
        for user in self.users:
            user.send_msg(message)


class User:
    def __init__(self, telegram_id, name):
        self.tg_id = telegram_id
        self.name = name
        self.room = None

    def get_word(self):
        if not self.room:
            return None
        else:
            word = self.room.get_word(self)
            return word

    def join_room(self, room_id):
        room = room_by_id(room_id)
        if not room:
            return 'Такой комнаты не существует'
        else:
            if self in room.users:
                return 'Вы уже находитесь в этой комнате'
            else:
                room.append(self)
                return 'Вы успешно присоединились к комнате'
    
    def start_round(self):
        if not self.room:
            return 'Вы не состоите в комнате'
        else:
            return self.room.start_round(self)

    def send_msg(self, message):
        TeleBot.send_message(self.tg_id, message)


def user_by_id(user_id):
    if user_id in USERS:
        return USERS[user_id]
    else:
        return None


def room_by_id(room_id):
    if room_id in ROOMS:
        return ROOMS[room_id]
    else:
        return None


# -----------------------------------------------------------------------------
def get_args(text, command_len, splitter='_'):
    return text[command_len:].split(splitter)


def warn_invalid_args(chat_id):
    TeleBot.send_message(chat_id, 'Некоректные аргументы. /commands_help для помощи')
# -----------------------------------------------------------------------------


@TeleBot.message_handler(func=lambda x: True)
def message_handler(message):
    chat = message.chat
    text = message.text
    user = user_by_id(chat.id)
    print('Got message from {}: {}'.format(chat.first_name, text))

    if user is None and text != '/start':
        TeleBot.send_message(chat.id, 'Напишите мне, пожалуйста, /start, чтобы я добавил вас в список пользователей')
        return 0

    if text == '/start':
        TeleBot.send_message(chat.id, 'Привет. Правила доступны по /rules, помощь - по /commands_help')
        USERS[chat.id] = User(chat.id, chat.first_name)

    if text.startswith('/join'):
        args = get_args(text, len('/join'))
        if len(args) > 1:
            warn_invalid_args(user.tg_id)
            return None

        room_id = args[0]
        ret = user.join_rooom(room_id)
        user.send_msg(ret)

    if text == '/round':
        ret = user.start_round()
        user.send_msg(ret)

    if text == '/gw':
        ret = user.get_word()
        user.send_msg(ret)

def main():
    global ROOMS
    global USERS
    ROOMS = {}
    USERS = {}
    print('Le go')
    TeleBot.polling(interval=3)


if __name__ == "__main__":
    main()
