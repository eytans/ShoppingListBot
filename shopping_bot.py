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

working_dir = sys.argv[1]
os.chdir(working_dir)

GENERAL_DATA = "main.data"
HELP = 'help'
ERROR_LOG = 'errors.log'
logging.basicConfig(filename=ERROR_LOG, level=logging.ERROR)

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

help_text = None
shopping_lists = {}
force = {'force_reply': True}


def read_data(data_path):
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


def update_data(data_path, data):
    if not os.path.exists(os.path.abspath(os.path.join(data_path, os.pardir))):
        os.makedirs(os.path.abspath(os.path.join(data_path, os.pardir)))
    with open(data_path, 'w') as data_file:
        for key, val in data.items():
            data_file.write(str(key) + '=' + str(val) + '\n')


def getsettingspath(chat_id):
    return get_listpath(chat_id).replace('list', 'settings')


def get_listpath(chat_id, list_name=None):
    if not os.path.exists(str(chat_id)):
        os.makedirs(str(chat_id))
    if list_name is None:
        list_name = 'list'
    return str(chat_id) + os.sep + list_name


def getlist(chat_id, list_name=None):
    global shopping_lists
    if chat_id in shopping_lists:
        return shopping_lists[chat_id]
    list_path = get_listpath(chat_id, list_name)
    if not os.path.exists(str(list_path)):
        return []
    with open(list_path, 'r') as list_file:
        list_lines = list_file.readlines()
    list_lines = [line.replace(os.linesep, '').replace('\r', '').replace('\n', '').strip() for line in list_lines]
    return list_lines


def updatelist(chat_id, new_list):
    global shopping_lists
    new_list = [item.replace(os.linesep, '').replace('\r', '').replace('\n', '').strip() for item in new_list]
    new_list = [item for item in new_list if item != '']
    shopping_lists[chat_id] = new_list
    with open(get_listpath(chat_id), 'w') as list_file:
        for item in new_list:
            list_file.write(item + '\n')


def sendmessage(chat_id, reply, reply_to=None, force=None):
    if reply == '':
        return
    try:
        bot.sendMessage(chat_id=chat_id, text=reply, reply_to_message_id=reply_to, reply_markup=force)
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
    global help_text
    if commands is not None:
        return commands

    if help_text is None:
        with open(HELP, 'r') as helpFile:
            help_text = "\n".join(helpFile.readlines())
    lines = help_text.splitlines()
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
def handle_help(text, chat_id, message_id):
    global help_text
    if help_text is None:
        with open(HELP, 'r') as helpFile:
            help_text = "\n".join(helpFile.readlines())
    sendmessage(chat_id, help_text)


def add_items(chat_id, items):
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


def handle_add(text, chat_id, message_id):
    global force
    items = getcleanitems(getitems(text, '/add'))
    if len(getitems(text, '/add')) == 0:
        sendmessage(chat_id, ADD_RESPONSE, message_id, force)
        return
    add_items(chat_id, items)


def handle_add_response(text, chat_id, message_id):
    items = getcleanitems(getitems(text, '/add'))
    add_items(chat_id, items)


def remove_items(items, chat_id):
    new_list = getlist(chat_id)
    count = 0
    for item in items:
        item = item.strip()
        if item in new_list:
            new_list.remove(item)
            count += 1
    updatelist(chat_id, new_list)
    sendmessage(chat_id, 'removed ' + str(count) + ' items')


def handle_remove(text, chat_id, message_id):
    global force
    items = getitems(text, '/remove')
    if len(items) == 0:
        sendmessage(chat_id, REMOVE_RESPONSE, message_id, force)
        return
    remove_items(items, chat_id)


def handle_remove_response(text, chat_id, message_id):
    global force
    items = getitems(text, '/remove')
    remove_items(items, chat_id)


def handle_showlist(text, chat_id, message_id):
    settings_path = getsettingspath(chat_id)
    settings = read_data(settings_path)
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


def handle_settings(text, chat_id, message_id):
    global force
    if (len(text.split()) == 1) or ((text.split()[1] != 'a') and (text.split()[1] != 'i')):
        sendmessage(chat_id, SETTINGS_RESPONSE, message_id, force)
        return
    order = text.split()[1]  # note that i use this expression in if
    settings_path = getsettingspath(chat_id)
    settings = {}
    settings[SORT_LIST_KEY] = (order == 'a')
    update_data(settings_path, settings)
    sendmessage(chat_id, 'ok')


def handle_clear(text, chat_id, message_id):
    updatelist(chat_id, [])
    sendmessage(chat_id, 'ok')


def get_reply_begining_by_text(text):
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


def handle_message(msg):
    global shopping_lists
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
        handle_add_response(text, chat_id, msg_id)
        if os.path.exists(get_listpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(get_listpath(chat_id, BACKUP_LIST_NAME))
    elif is_reply and reply_text.startswith(REMOVE_RESPONSE):
        handle_remove_response(text, chat_id, msg_id)
        if os.path.exists(get_listpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(get_listpath(chat_id, BACKUP_LIST_NAME))
    elif is_reply and reply_text.startswith(SETTINGS_RESPONSE):
        handle_settings(text, chat_id, msg_id)
    elif is_reply and reply_text.startswith(EDIT_RESPONSE):
        new_list = getcleanitems(getitems(text, None))
        if os.path.exists(get_listpath(chat_id)):
            shutil.copy2(get_listpath(chat_id), get_listpath(chat_id, BACKUP_LIST_NAME))
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
        handle_help(text, chat_id, msg_id)
    elif text.startswith('/add'):
        text = text.replace('/add@eytans_shopping_bot', '/add')
        handle_add(text, chat_id, msg_id)
        if os.path.exists(get_listpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(get_listpath(chat_id, BACKUP_LIST_NAME))
    elif text.startswith('/remove'):
        text = text.replace('/remove@eytans_shopping_bot', '/remove')
        handle_remove(text, chat_id, msg_id)
        if os.path.exists(get_listpath(chat_id, BACKUP_LIST_NAME)):
            os.remove(get_listpath(chat_id, BACKUP_LIST_NAME))
    elif text.startswith('/showlist'):
        handle_showlist(text, chat_id, msg_id)
    elif text.startswith('/settings'):
        handle_settings(text, chat_id, msg_id)
    elif text.startswith('/clear'):
        if os.path.exists(get_listpath(chat_id)):
            shutil.copy2(get_listpath(chat_id), get_listpath(chat_id, BACKUP_LIST_NAME))
        handle_clear(text, chat_id, msg_id)
    elif text.startswith('/edit'):
        text = '/showlist'
        handle_showlist(text, chat_id, msg_id)
        sendmessage(chat_id, EDIT_RESPONSE, msg_id, force)
    elif text.startswith('/undoedit'):
        if not os.path.exists(get_listpath(chat_id, BACKUP_LIST_NAME)):
            sendmessage(chat_id,
                        'Sorry, i dont have a backup. if you didnt edit or used add/remove i wouldnt have one..')
        else:
            shutil.copy2(get_listpath(chat_id, BACKUP_LIST_NAME), get_listpath(chat_id))
            os.remove(get_listpath(chat_id, BACKUP_LIST_NAME))
            del shopping_lists[chat_id]
            sendmessage(chat_id, 'ok')


data = read_data(GENERAL_DATA)

if SHOPPING_BOT_TOKEN_KEY not in data:
    print('error: no bot token. cant be a bot without a bot')
    exit(1)
shopping_bot_token = data[SHOPPING_BOT_TOKEN_KEY].strip()
bot = telepot.Bot(token=shopping_bot_token)

bot.message_loop(handle_message, run_forever=True)
