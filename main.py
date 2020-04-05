#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from threading import Thread
from random import randint, choice, shuffle
from time import time, sleep
import telebot


TELEBOT_TOKEN = open('tg.tkn').read()
TeleBot = telebot.TeleBot(TELEBOT_TOKEN)
ADMIN_ID = [150486866]

USERS = {}
ROOMS = {}
EVENTS = set()

HELP = open('com_help.txt', 'r').read()


class Event:
    def __init__(self, init_time, length, target, *args):
        self.init_time = init_time
        self.end_time = init_time + length
        self.target = target
        self.args = args

    def check(self, cur_time):
        if cur_time > self.end_time:
            self.target(*self.args)
            return True
        else:
            return False


class Room:
    def __init__(self, room_id, round_time, bonus_time, admin):
        self.id = room_id
        self.admin = admin

        self.dict = []
        self.guessed = []
        self.players = []

        self.round_time = round_time
        self.bonus_time = bonus_time
        self.offset_time = 0.1

        self.last_round_time = 0.0
        self.cur_player = None
        self.last_word = None

        self.game_running = False
        self.next_player = 0
        self.players_cnt = 0
        self.player_offset = 1

    def shift_pair(self):
        self.next_player = (self.next_player + 1) % self.players_cnt
        if not self.next_player:
            self.player_offset = max((self.player_offset + 1) % self.players_cnt, 1)

    def get_next_pair(self):
        next_player = self.players[self.next_player]
        next_guesser = self.players[(self.next_player + self.player_offset) % self.players_cnt]
        return [next_player, next_guesser]

    def start_game(self):
        self.game_running = True
        self.players_cnt = len(self.players)
        self.next_player = 0
        self.player_offset = 1

    def stop_game(self):
        self.game_running = False

    def add_word(self, word):
        self.dict.append(word)

    def get_word(self, player):
        if (self.cur_player is not player):
            return 'Сейчас не ваш раунд'

        t = time()
        if t - self.last_round_time < self.round_time + self.bonus_time:
            self.guess_word(self.last_word, player)
            if t - self.last_round_time > self.round_time:
                return 'Слово угадано, но время раунда закончилось'
            else:
                if not self.dict:
                    return 'Слова закончились'

                word = choice(self.dict)
                self.last_word = word
                return word

        return 'Сейчас нет активного раунда'

    def guess_word(self, word, player):
        if not word:
            return None

        if word in self.dict:
            del self.dict[self.dict.index(word)]
            self.guessed.append(word)
            self.send_msg('Игрок {} обьяснил слово {}'.format(player.name, word))
        else:
            self.send_msg('Игрок {} не мог обьяснять слово {}!'.format(player.name, word))

    def add_player(self, player):
        self.players.append(player)

    def reset(self):
        self.dict = self.dict + self.guessed
        self.guessed = []

    def start_round(self, player):
        if not self.game_running:
            return 'В вашей комнате еще не начата игра'

        next_player, next_guesser = self.get_next_pair()
        if next_player is not player:
            return 'Следующий раунд: {} обьясняет {}'.format(next_player.name, next_guesser.name)

        t = time()
        if t - self.last_round_time < self.round_time + self.bonus_time:
            return 'Раунд уже идет! Обьясняешь: ' + self.last_word

        if not self.dict:
            return 'Слова закончились! Жми /reset, чтобы начать ту же шляпу заново'

        self.send_msg(next_player.name + ' обьясняет ' + next_guesser.name + '. Поехали!')
        t = time()
        self.last_round_time = t
        self.cur_player = player
        EVENTS.add(Event(t, self.round_time - self.offset_time, self.send_msg, player.name + ' уже не может обьяснять'))
        EVENTS.add(Event(t, self.round_time + self.bonus_time - self.offset_time, self.send_msg, 'Раунд игрока ' + player.name + ' закончен'))
        EVENTS.add(Event(t, self.round_time + self.bonus_time, self.shift_pair))
        EVENTS.add(Event(t, self.round_time + self.bonus_time - self.offset_time, self.send_msg, 'Следующий раунд: {} обьясняет {}'.format(next_player.name, next_guesser.name)))
        
        self.last_word = None
        word = self.get_word(player)
        return word + '\n/word'

    def send_msg(self, message):
        for user in self.players:
            user.send_msg(message)


class User:
    def __init__(self, telegram_id, name):
        self.tg_id = telegram_id
        self.name = name
        self.room = None

    def set_name(self, name):
        self.name = name
        return 'Имя успешно изменено на ' + name

    def get_word(self):
        if not self.room:
            return 'Вы не состоите в комнате'
        else:
            word = self.room.get_word(self)
            return word

    def join_room(self, room_id):
        room = room_by_id(room_id)
        if not room:
            return 'Такой комнаты не существует'
        else:
            if self in room.players:
                return 'Вы уже находитесь в этой комнате'
            else:
                self.leave_room()
                room.players.append(self)
                self.room = room
                return 'Вы успешно присоединились к комнате'

    def leave_room(self):
        if not self.room:
            return 'Чтобы покинуть комнату, в нее вначале надо зайти'
        else:
            room = self.room
            if self in room.players:
                if room.game_running:
                    return 'Вы не можете покинуть идущую игру. Остановите ее с помощью /stop_game'
                del room.players[room.players.index(self)]
            self.room = None
            return 'Вы успешно покинули комнату {}'.format(room.id)
    
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
def get_args(text, command_len, sep='_'):
    return text[command_len:].split(sep)

def polish_args(args, requirements):
    ret = args[::]
    if len(args) != len(requirements):
        return None
    try:
        for i in range(len(args)):
            ret[i] = type(requirements[i])(ret[i])
    except Exception:
        return None
    return ret


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
        return

    if text == '/start':
        TeleBot.send_message(chat.id, 'Привет! Помощь по командам доступна по /help')
        USERS[chat.id] = User(chat.id, chat.first_name)

    if text == '/help':
        ret = HELP
        user.send_msg(ret)

    if text.startswith('/setname'):
        args = get_args(text, len('/setname') + 1)
        name = args[0]
        ret = user.set_name(name)
        user.send_msg(ret)

    if text.startswith('/join'):
        args = get_args(text, len('/join') + 1)
        args = polish_args(args, [''])
        if not args:
            warn_invalid_args(user.tg_id)
            return

        room_id = args[0]
        ret = user.join_room(room_id)
        user.send_msg(ret)

    if text == '/leave':
        ret = user.leave_room()
        user.send_msg(ret)

    if text == '/start_game':
        room = user.room
        if not room:
            ret = 'Вы не состоите в комнате'
            user.send_msg(ret)
            return
        if user is not room.admin:
            ret = 'Вы не админ этой комнаты'
            user.send_msg(ret)
            return

        room.start_game()
        ret = 'Игра в комнате {} началась'.format(room.id)
        room.send_msg(ret)

    if text == '/stop_game':
        room = user.room
        if not room:
            ret = 'Вы не состоите в комнате'
            user.send_msg(ret)
            return
        if user is not room.admin:
            ret = 'Вы не админ этой комнаты'
            user.send_msg(ret)
            return

        room.stop_game()
        ret = 'Игра в комнате {} остановлена. /reset для возвращения угаданных слов в шляпу'.format(room.id)
        room.send_msg(ret)

    if text == '/players':
        room = user.room
        if not room:
            ret = 'Вы не состоите в комнате'
            user.send_msg(ret)
            return

        ret = 'Игроки комнаты ' + room.id + ': '
        players_cnt = len(room.players)
        for i in range(players_cnt):
            ret += room.players[i].name
            if i != players_cnt - 1:
                ret += ', '
        user.send_msg(ret)

    if text == '/reset':
        room = user.room
        if not room:
            ret = 'Вы не состоите в комнате'
            user.send_msg(ret)
            return
        if user is not room.admin:
            ret = 'Вы не админ этой комнаты'
            user.send_msg(ret)
            return

        if room.game_running:
            ret = 'Нельзя возвращать слова в шляпу, пока идет игра. Остановите ее с помощью /stop_game'
            user.send_msg(ret)
        else:
            room.reset()
            ret = 'Все слова снова помещены в шляпу и тщательно перемешаны. Виновник - {}'.format(user.name)
            room.send_msg(ret)

    if text == '/round':
        ret = user.start_round()
        user.send_msg(ret)

    if text == '/word':
        ret = user.get_word()
        user.send_msg(ret  + '\n/word')

    if text.startswith('/new_room'):
        args = get_args(text, len('/new_room') + 1)
        args = polish_args(args, ['', 0, 0])
        if not args:
            warn_invalid_args(user.tg_id)
            return

        room_id = args[0]
        round_time = args[1]
        bonus_time = args[2]
        room = Room(room_id, round_time, bonus_time, user)
        ROOMS[room_id] = room

        ret = 'Комната успешно создана. ' + '/join_' + room_id
        user.send_msg(ret)

    if text.startswith('/new_words'):
        if not user.room:
            ret = 'Вы не состоите в комнате'
            user.send_msg(ret)
            return

        args = get_args(text, len('/new_words') + 1, sep='\n')
        cnt = len(args)
        for word in args:
            if len(word) >= 2:
                print('word "{}" added to room "{}"'.format(word, user.room.id))
                user.room.add_word(word)
            else:
                cnt -= 1

        user.room.send_msg('{} добавил слов в шляпу, их {}'.format(user.name, cnt))


def event_check():
    while True:
        t = time()
        events_to_delete = []
        for event in EVENTS:
            if event.check(t):
                events_to_delete.append(event)
        for event in events_to_delete:
            EVENTS.remove(event)

        sleep(0.3)


event_check_thread = Thread(target=event_check)


def main():
    global ROOMS
    global USERS
    ROOMS = {}
    USERS = {}
    print('Le go')
    event_check_thread.start()
    TeleBot.polling(interval=0.5)


if __name__ == "__main__":
    main()
