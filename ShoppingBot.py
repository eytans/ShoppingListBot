__author__ = 'eytan'

import telepot
import sys
import os
import time
import shutil
import logging
import re
import traceback

if len(sys.argv) < 2:
    print("bad arguments. need working folder. exiting")
    exit(1)

workingDir = sys.argv[1]
os.chdir(workingDir)

GENERAL_DATA = "main.data"
HELP = 'help'
ERROR_LOG = 'errors.log'
error_log = logging.basicConfig(filename=ERROR_LOG, level=logging.ERROR)

ADD_RESPONSE = 'What item do you want to add to the list?'
REMOVE_RESPONSE = 'What item do you want to remove from the list?'
SETTINGS_RESPONSE = 'Do you want to sort the list alphabetically or by insertion order? <a = alphabetically, i = insertion>'
EDIT_RESPONSE = 'Please send the new list after editing it in your next message. (you can find current list above). for example if the list is milk and tomatos send:\nmilk\ntoamtos'

SHOPPING_BOT_TOKEN_KEY = 'token_key'
LAST_UPDATE_KEY = 'last_update'
SORT_LIST_KEY = 'sort_list'

LIST_MAX_SIZE = 300
ITEM_MAX_SIZE = 100
BACKUP_LIST_NAME = 'list.bak'

helpText = None
shoppingLists = {}
force = {'force_reply': True}

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
        for key, val in data.items():
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
    list_lines = [line.replace(os.linesep, '').replace('\r', '').replace('\n', '').strip() for line in list_lines]
    return list_lines


def updatelist(chat_id, new_list):
    global shoppingLists
    new_list = [item.replace(os.linesep, '').replace('\r', '').replace('\n', '').strip() for item in new_list]
    new_list = [item for item in new_list if item != '']
    shoppingLists[chat_id] = new_list
    with open(getlistpath(chat_id), 'w') as list_file:
        for item in new_list:
            list_file.write(item + '\n')


def sendmessage(chat_id, reply, reply_to=None, force=None):
    if reply == '':
        return
    try:
        bot.sendMessage(chat_id=chat_id, text=reply,  reply_to_message_id=reply_to, reply_markup=force)
    except:
        print(traceback.format_exc())
        if error_log is not None:
            error_log.exception("Error!")
        raise RuntimeError('send message error')


def getitems(text, command=None):
    items = text.replace(os.linesep, '\n').split('\n')
    if command is not None:
        items = [items[0].replace(command, '')] + items[1:]
    items = [item.strip() for item in items]
    if items[0] == '':
        items = items[1:]
    return items


commands = None
def getCommands():
    global commands
    global helpText
    if commands is not None:
        return commands

    if helpText is None:
        with open(HELP, 'r') as helpFile:
            helpText = "\n".join(helpFile.readlines())
    lines = helpText.splitlines()
    res = []
    for line in lines:
        if '-' not in line:
            continue
        res.append(line.split('-')[0].strip())
    commands = res
    return res


pattern = None
def getcleanitems(items):
    global pattern
    commands = getCommands()
    if pattern is None:
        pattern = '|'.join(commands)
    res = []
    for item in items:
        temp = re.sub(pattern, '', item).strip()
        if temp != '':
            res.append(temp)
    return res


# returns the answer string
def handleHelp(text, chat_id, message_id):
    global helpText
    if helpText is None:
        with open(HELP, 'r') as helpFile:
            helpText = "\n".join(helpFile.readlines())
    sendmessage(chat_id, helpText)


def addItemsToList(chat_id, items):
    orig_items_len = len(items)
    current = getlist(chat_id)
    if (len(current) + len(items)) > LIST_MAX_SIZE:
        items = items[(len(items) - (LIST_MAX_SIZE - len(current))):]
    reply = 'added ' + str(len(items)) + ' items.'
    if orig_items_len > len(items):
        reply += ' as list reached max size (300 items).'
    for item in items:
        if len(item) > ITEM_MAX_SIZE:
            reply = reply + ' some items were shortened. (max item size = ' + str(ITEM_MAX_SIZE) + ')'
            break
    items = [item[:100] for item in items]
    updatelist(chat_id, current + items)
    sendmessage(chat_id, reply)


def handleAdd(text, chat_id, message_id):
    global force
    items = getcleanitems(getitems(text, '/add'))
    if len(getitems(text, '/add')) == 0:
        sendmessage(chat_id, ADD_RESPONSE, message_id, force)
        return
    addItemsToList(chat_id, items)


def handleAddResponse(text, chat_id, message_id):
    items = getcleanitems(getitems(text, '/add'))
    addItemsToList(chat_id, items)


def removeItemsFromList(items, chat_id):
    new_list = getlist(chat_id)
    count = 0
    for item in items:
        item = item.strip()
        if item in new_list:
            new_list.remove(item)
            count += 1
    updatelist(chat_id, new_list)
    sendmessage(chat_id, 'removed ' + str(count) + ' items')


def handleRemove(text, chat_id, message_id):
    global force
    items = getitems(text, '/remove')
    if len(items) == 0:
        sendmessage(chat_id, REMOVE_RESPONSE, message_id, force)
        return
    removeItemsFromList(items, chat_id)


def handleRemoveResponse(text, chat_id, message_id):
    global force
    items = getitems(text, '/remove')
    removeItemsFromList(items, chat_id)


def handleShowlist(text, chat_id, message_id):
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
            key = ''.join([i for i in name if not i.isdigit()]).strip()
            if key not in dic:
                dic[key] = []
                names.append(key)
            dic[key].append(name)
        names.sort()
        result = []
        for key in names:
            for name in dic[key]:
                result.append(name)
    reply = '\n'.join(result)
    if len(result) == 0:
        reply = 'nothing to show'
    sendmessage(chat_id, reply)


def handleSettings(text, chat_id, message_id):
    global force
    if (len(text.split()) == 1) or ((text.split()[1] != 'a') and (text.split()[1] != 'i')):
        sendmessage(chat_id, SETTINGS_RESPONSE, message_id, force)
        return
    order = text.split()[1] # note that i use this expression in if
    settings_path = getsettingspath(chat_id)
    settings = {}
    settings[SORT_LIST_KEY] = (order == 'a')
    updateData(settings_path, settings)
    sendmessage(chat_id, 'ok')


def handleClear(text, chat_id, message_id):
    updatelist(chat_id, [])
    sendmessage(chat_id, 'ok')


def getReplyBeginingByText(text):
    if text == ADD_RESPONSE:
        return '/add '
    elif text == REMOVE_RESPONSE:
        return '/remove '
    elif text == SETTINGS_RESPONSE:
        return '/settings '
    elif text.startswith(EDIT_RESPONSE):
        return 'editreply'
    else:
        return ''


def handleMessage(msg):
    global shoppingLists
    global error_log
    global force
    if msg is None:
        return
    msg_id = msg['message_id']
    content_type, chat_type, chat_id = telepot.glance(msg)
    # handle new group by printing hello and help.
    text = msg['text']
    is_reply = 'reply_to_message' in msg
    if is_reply:
        reply_text = msg['reply_to_message']['text']
    if 'group_chat_created' in msg and msg['group_chat_created'] == 'True':
        sendmessage(chat_id, 'Hi, im here to help you shop. if you want more info just write /help')
    if is_reply and reply_text.startswith(ADD_RESPONSE):
        handleAddResponse(text, chat_id, msg_id)
        if os.path.exists(getlistpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(getlistpath(chat_id, BACKUP_LIST_NAME))
    elif is_reply and reply_text.startswith(REMOVE_RESPONSE):
        handleRemoveResponse(text, chat_id, msg_id)
        if os.path.exists(getlistpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(getlistpath(chat_id, BACKUP_LIST_NAME))
    elif is_reply and reply_text.startswith(SETTINGS_RESPONSE):
        handleSettings(text, chat_id, msg_id)
    elif is_reply and reply_text.startswith(EDIT_RESPONSE):
        new_list = getcleanitems(getitems(text, None))
        if os.path.exists(getlistpath(chat_id)):
            shutil.copy2(getlistpath(chat_id), getlistpath(chat_id, BACKUP_LIST_NAME))
        reply = 'ok'
        if len(new_list) > LIST_MAX_SIZE:
            new_list = new_list[:LIST_MAX_SIZE]
            reply = 'list too long. added only the ' + str(LIST_MAX_SIZE) + ' first items.'
        for item in new_list:
            if len(item) > ITEM_MAX_SIZE:
                reply = reply + ' some items were shortened. (max item size = ' + str(ITEM_MAX_SIZE) + ')'
                break
        new_list = [item[:100] for item in new_list]
        updatelist(chat_id, new_list)
        sendmessage(chat_id, reply)
    elif text.startswith('/help'):
        handleHelp(text, chat_id, msg_id)
    elif text.startswith('/add'):
        text = text.replace('/add@eytans_shopping_bot', '/add')
        handleAdd(text, chat_id, msg_id)
        if os.path.exists(getlistpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(getlistpath(chat_id, BACKUP_LIST_NAME))
    elif text.startswith('/remove'):
        text = text.replace('/remove@eytans_shopping_bot', '/remove')
        handleRemove(text, chat_id, msg_id)
        if os.path.exists(getlistpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(getlistpath(chat_id, BACKUP_LIST_NAME))
    elif text.startswith('/showlist'):
        handleShowlist(text, chat_id, msg_id)
    elif text.startswith('/settings'):
        handleSettings(text, chat_id, msg_id)
    elif text.startswith('/clear'):
        if os.path.exists(getlistpath(chat_id)):
            shutil.copy2(getlistpath(chat_id), getlistpath(chat_id, BACKUP_LIST_NAME))
        handleClear(text, chat_id, msg_id)
    elif text.startswith('/edit'):
        text = '/showlist'
        handleShowlist(text, chat_id, msg_id)
        sendmessage(chat_id, EDIT_RESPONSE, msg_id, force)
    elif text.startswith('/undoedit'):
        if not os.path.exists(getlistpath(chat_id, BACKUP_LIST_NAME)):
            sendmessage(chat_id, 'Sorry, i dont have a backup. if you didnt edit or used add/remove i wouldnt have one..')
        else:
            shutil.copy2(getlistpath(chat_id, BACKUP_LIST_NAME), getlistpath(chat_id))
            os.remove(getlistpath(chat_id, BACKUP_LIST_NAME))
            del shoppingLists[chat_id]
            sendmessage(chat_id, 'ok')


data = readData(GENERAL_DATA)

if SHOPPING_BOT_TOKEN_KEY not in data:
    print('error: no bot token. cant be a bot without a bot')
    exit(1)
shopping_bot_token = data[SHOPPING_BOT_TOKEN_KEY].strip()
bot = telepot.Bot(token=shopping_bot_token)

bot.message_loop(handleMessage, run_forever=True)

