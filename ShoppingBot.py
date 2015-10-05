__author__ = 'eytan'

import telegram
import sys
import os
import time
from string import digits
import shutil

if len(sys.argv) < 2:
    print("bad arguments. need working folder. exiting")
    exit(1)

workingDir = sys.argv[1]
os.chdir(workingDir)

GENERAL_DATA = "main.data"
HELP = 'help'

ADD_RESPONSE = 'What item do you want to add to the list?'
REMOVE_RESPONSE = 'What item do you want to remove from the list?'
SETTINGS_RESPONSE = 'Do you want to sort the list alphabetically or by insertion order? <a = alphabetically, i = insertion>'

SHOPPING_BOT_TOKEN_KEY = 'token_key'
LAST_UPDATE_KEY = 'last_update'
SORT_LIST_KEY = 'sort_list'

LIST_MAX_SIZE = 300

helpText = None
shoppingLists = {}


def readData(data_path):
    data = {}
    if os.path.exists(data_path):
        with open(data_path, 'r') as dataFile:
            lines = dataFile.readlines()
            for line in lines:
                if line.strip() == '':
                    continue
                key, val = line.split('=')
                data[key] = val
    return data


def updateData(data_path, data):
    if not os.path.exists(os.path.abspath(os.path.join(data_path, os.pardir))):
        os.mkdirs(os.path.abspath(os.path.join(data_path, os.pardir)))
    with open(data_path, 'w') as data_file:
        for key, val in data.iteritems():
            data_file.write(str(key) + '=' + str(val) + '\n')


def getsettingspath(chat_id):
    return getlistpath(chat_id).replace('list', 'settings')


def getlistpath(chat_id, list_name=None):
    if not os.path.exists(str(chat_id)):
        os.makedirs(str(chat_id))
    if list_name is None:
        list_name = 'list'
    return str(chat_id) + os.sep + list_name


def getlist(chat_id, list_name=None):
    global shoppingLists
    if chat_id in shoppingLists:
        return shoppingLists[chat_id]
    list_path = getlistpath(chat_id, list_name)
    if not os.path.exists(str(list_path)):
        return []
    with open(list_path, 'r') as list_file:
        list_lines = list_file.readlines()
    list_lines = [line.strip() for line in list_lines]
    return list_lines


def updatelist(chat_id, new_list):
    global shoppingLists
    new_list = [item.strip() for item in new_list]
    shoppingLists[chat_id] = new_list
    with open(getlistpath(chat_id), 'w') as list_file:
        for item in new_list:
            list_file.write(item + os.linesep)


# returns the answer string
def helpresult(text):
    global helpText
    if text.startswith('/help'):
        if helpText is None:
            with open(HELP, 'r') as helpFile:
                helpText = "\n".join(helpFile.readlines())
        return False, helpText
    else:
        return False, ''


def getitems(text, command):
    items = text.replace(os.linesep, '\n').split('\n')
    items = [items[0].replace(command, '')] + items[1:]
    items = [item.strip() for item in items]
    if items[0] == '':
        items = items[1:]
    return items


def addresult(text, chat_id):
    if not text.startswith('/add'):
        return False, ''
    items = getitems(text, '/add')
    if len(items) == 0:
        return True, ADD_RESPONSE
    current = getlist(chat_id)
    if (len(current) + len(items)) > LIST_MAX_SIZE:
        items = items[(len(items) - (LIST_MAX_SIZE - len(current))):]
    updatelist(chat_id, current + items)
    return False, 'added ' + str(len(items)) + ' items'


def removeresult(text, chat_id):
    if not text.startswith('/remove'):
        return False, ''
    items = getitems(text, '/remove')
    if len(items) == 0:
        return True, REMOVE_RESPONSE
    new_list = getlist(chat_id)
    count = 0
    for item in items:
        item = item.strip()
        if item in new_list:
            new_list.remove(item)
            count += 1
    updatelist(chat_id, new_list)
    return False, 'removed ' + str(count) + ' items'


def showlistresult(text, chat_id):
    if not text.startswith('/showlist'):
        return False, ''
    settings_path = getsettingspath(chat_id)
    settings = readData(settings_path)
    sort_list = True
    if SORT_LIST_KEY in settings:
        sort_list = bool(settings[SORT_LIST_KEY])
    result = getlist(chat_id)
    if sort_list:
        names = []
        dic = {}
        for name in result:
            key = name.translate(None, digits).strip()
            if key not in dic:
                dic[key] = []
            names.append(key)
            dic[key].append(name)
        names.sort()
        result = []
        for key in names:
            for name in dic[key]:
                result.append(name)
    if len(result) == 0:
        return False, 'nothing to show'
    return False, '\n'.join(result)


def settingsresult(text, chat_id):
    if not text.startswith('/settings'):
        return False, ''
    if len(text.split()) == 1:
        return True, SETTINGS_RESPONSE
    order = text.split()[1]
    if order != 'a' and order != 'i':
        return True, SETTINGS_RESPONSE
    settings_path = getsettingspath(chat_id)
    settings = {}
    settings[SORT_LIST_KEY] = (order == 'a')
    updateData(settings_path, settings)
    return False, 'ok'


def clearsresult(text, chat_id):
    if not text.startswith('/clear'):
        return False, ''
    updatelist(chat_id, [])
    return False, 'ok'


def getReplyBeginingByText(text):
    if text == ADD_RESPONSE:
        return '/add '
    elif text == REMOVE_RESPONSE:
        return '/remove '
    elif text == SETTINGS_RESPONSE:
        return '/settings '
    elif text.startswith('Please send the list after editing it in your next message.\n Current list:\n'):
        return 'editreply'
    else:
        return ''


def handleMessage(chat_id, message):
    global shoppingLists
    if message is None:
        return
    text = message.text
    if message.reply_to_message:
        text = getReplyBeginingByText(message.reply_to_message.text) + text
    if text.startswith('/help'):
        force_reply, reply = helpresult(text)
    elif text.startswith('/add'):
        text = text.replace('/add@eytans_shopping_bot', '/add')
        force_reply, reply = addresult(text, chat_id)
    elif text.startswith('/remove'):
        text = text.replace('/remove@eytans_shopping_bot', '/remove')
        force_reply, reply = removeresult(text, chat_id)
    elif text.startswith('/showlist'):
        force_reply, reply = showlistresult(text, chat_id)
    elif text.startswith('/settings'):
        force_reply, reply = settingsresult(text, chat_id)
    elif text.startswith('/clear'):
        force_reply, reply = clearsresult(text, chat_id)
    elif text.startswith('/edit'):
        text = '/showlist'
        force_reply, reply = showlistresult(text, chat_id)
        reply = 'Please send the list after editing it in your next message.\n Current list:\n' + reply
        force_reply = True
    elif text.startswith('editreply'):
        new_list = getitems(text, 'editreply')
        shutil.copy2(getlistpath(chat_id), getlistpath(chat_id, 'list.bak'))
        updatelist(chat_id, new_list)
    elif text.startswith('/undoedit'):
        if not os.path.exists(getlistpath(chat_id, 'list.bak')):
            force_reply = False
            reply = 'Sorry, i dont have a backup. if you didnt edit or used add/remove i wouldnt have one..'
        else:
            shutil.copy2(getlistpath(chat_id, 'list.bak'), getlistpath(chat_id))
            os.remove(getlistpath(chat_id, 'list.bak'))
            force_reply = False
            reply = 'ok'
            del shoppingLists[chat_id]
    else:
        force_reply, reply = False, ''

    if force_reply and len(reply) == 0:
        print('error: bad parmaeters for: ' + message.text)
        return

    force = None
    if force_reply:
        force = telegram.ForceReply(selective=True)
    reply_to = message.message_id
    if len(reply) == 0:
        return
    try:
        bot.sendMessage(chat_id=chat_id, text=reply, reply_to_message_id=reply_to, reply_markup=force)
    except:
        print('error: cant send message')


data = readData(GENERAL_DATA)
last_update = 0
if LAST_UPDATE_KEY in data:
    last_update = int(data[LAST_UPDATE_KEY])

if SHOPPING_BOT_TOKEN_KEY not in data:
    print('error: no bot token. cant be a bot without a bot')
    exit(1)
shopping_bot_token = data[SHOPPING_BOT_TOKEN_KEY].strip()
bot = telegram.Bot(token=shopping_bot_token)

# like do while
while True:
    updates = bot.getUpdates(offset=(last_update))
    while len(updates) > 0:
        last_update = 0
        for update in updates:
            # finish handeling the update by raising the last update then send message
            chat_id = update.message.chat_id
            try:
                # make sure not to send empty message
                handleMessage(chat_id, update.message)
            finally:
                last_update = max(last_update, update.update_id)
        last_update += 1
        updates = bot.getUpdates(offset=(last_update))
    time.sleep(1)
