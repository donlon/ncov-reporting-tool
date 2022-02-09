#!/usr/bin/env python3

import json
import os
import time
from datetime import datetime
from email import utils as email_utils

from retry import retry
import requests
import schedule
import yaml

data_dir = os.getenv('NRTOOL_DATA_PATH') or '/data'
log_dir = os.getenv('NRTOOL_LOG_PATH') or os.path.join(data_dir, 'log')


def log(task_id, date, payload, response):
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, 'report_%s_%s.log' % (str(task_id), date)), 'w', encoding='utf-8') as f:
        json.dump({
            'task_id': task_id,
            'payload': payload,
            'response': response
        }, f, ensure_ascii=False, indent=4)


@retry(exceptions=requests.exceptions.RequestException, tries=10, delay=10)
def send_request_2(post_data, cookie):
    r = requests.post('https://app.bupt.edu.cn/ncov/wap/default/save',
                      headers={
                          'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Mobile Safari/532.12',
                          'DNT': '1',
                          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                          'Cookie': cookie,
                          'X-Requested-With': 'XMLHttpRequest',
                      }, data=post_data)
    print(r.json())
    return r


def send_request(task_id, data, uid, cookie):
    now = datetime.now()

    date = now.strftime('%Y%m%d')  # '20200927'
    created = str(int(time.time()))

    post_data = {
        **data,
        'uid': uid,
        'date': date,
        'created': created,
        'id': 8749065
    }
    print(json.dumps(post_data))

    r = send_request_2(post_data, cookie)

    log(task_id, date, post_data, r.json())


def do_task(payload):
    print('do task:')
    print(json.dumps(payload))

    with open(payload['profile_path'], 'r', encoding='utf-8') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    send_request(payload['id'], data, payload['uid'], payload['cookie'])


def create_task(task):
    payload = {}
    if 'id' not in task:
        print('Error: id is not definded')
        return
    if 'uid' not in task:
        print('Error: uid is not definded')
        return
    if 'cookie' not in task:
        print('Error: cookie is not definded')
        return
    if 'profile' not in task:
        print('Error: profile is not definded')
        return
    payload['id'] = task['id']
    payload['uid'] = task['uid']
    payload['cookie'] = task['cookie']

    profile_path = os.path.join(data_dir, task['profile'])
    if not os.path.exists(profile_path):
        print('Error: id=%s: profile \'%s\' is not found' % (str(payload['id']), profile_path))
        return
    with open(profile_path, 'r', encoding='utf-8') as f:
        try:
            yaml.load(f, Loader=yaml.FullLoader)
        except yaml.parser.ParserError as e:
            print('Invalid YAML file %s: %s' % (profile_path, e))
            return

    payload['profile_path'] = profile_path

    if 'time' not in task:
        send_time = '07:00'
    else:
        send_time = task['time']
    payload['time'] = send_time

    print('Loaded task: id=%s, profile=%s, uid=%d, time=%s' %
          (str(payload['id']), profile_path, payload['uid'], send_time))
    schedule.every().day.at(send_time).do(do_task, payload)
    return True


def load_tasks():
    path = os.path.join(data_dir, 'tasks.yaml')
    if not os.path.exists(path):
        print('Task configuration is not exist: %s' % path)
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        if 'tasks' not in data:
            print('Invalid configuration file')
            return
        for task in data['tasks']:
            if not create_task(task):
                return
    return True


def fetch_server_time():
    r = requests.get('https://app.bupt.edu.cn/ncov/wap/default/index')
    t = email_utils.parsedate(r.headers['Date'])
    return time.mktime(t)


# server.timestamp - local.timestamp (in secs)
server_time_offset = 0


@retry(exceptions=Exception, tries=10, delay=20)
def update_server_time_offset():
    server_time_offset = fetch_server_time() - datetime.utcnow().timestamp()
    print('Server time offset: ' + str(server_time_offset))


if __name__ == "__main__":
    print('Program started...')

    schedule.every().day.at('23:00').do(update_server_time_offset)

    if not load_tasks():
        print('Can\'t load tasks')
        exit(1)

    print('Waiting for tasks...')
    while True:
        schedule.run_pending()
        time.sleep(1)
