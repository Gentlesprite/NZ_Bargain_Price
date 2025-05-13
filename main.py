# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/8/9 8:22
# File:main.py
import json
import time
import sched
import datetime

import requests
import urllib.parse
import urllib.request
from loguru import logger

from config import *

logger.add('reduce_price_log.log', rotation='5 MB', encoding='utf-8', enqueue=True, retention='10 days')


def read_last_result():
    with open('last_result.txt', 'r') as f:
        res = f.read()
    return res


def record_last_result(content: str):
    if content == '':
        logger.success('上次领取记录已清除！')
    with open('last_result.txt', 'w') as f:
        f.write(content)


def one_more_thing(func):
    def inner(*args, **kwargs):
        last_result = read_last_result()
        if last_result == 'MODULE OK':
            now_time = datetime.datetime.now()
            midnight_time = datetime.datetime.combine(now_time.date(), datetime.time())
            if now_time >= midnight_time:
                midnight_time += datetime.timedelta(days=1)
            # 计算距离午夜还有多久
            time_until_midnight = midnight_time - now_time
            logger.info(f'检测到今日资格已用尽,将在明日开启下一次执行!')
            time.sleep(time_until_midnight.total_seconds())
            record_last_result('')
            task(schedule_times)
            return
        res = func(*args, **kwargs)
        status = res.get('flowRet').get('sMsg')
        try:
            if status == '抱歉，您今日还未登录！':
                record_last_result(status)
                logger.warning(status)
            elif status == '今日已领取！':
                record_last_result('MODULE OK')
                logger.info(status)
            elif status == 'MODULE OK':
                success_code = res.get('modRet').get('sMsg')
                if success_code:
                    sc_send(text=success_code, desp=f'日期:{str(datetime.datetime.now())}', key=push_key)
                    record_last_result(status)
                    logger.success(status)
            else:
                try:
                    logger.warning(status)
                except Exception as e:
                    logger.error(f'{res}\n{e}')
        except Exception as e:
            logger.error(e)
        finally:
            task(schedule_times)
        return res

    return inner


@one_more_thing
def reduce_price():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36 QIHU 360SE',
        'cookie': cookies,
        'referer': 'https://nz.qq.com/'}

    res = requests.post(url=url, data=post_data, headers=headers)
    res.encoding = res.apparent_encoding

    return json.loads(res.text)


def sc_send(text, desp='', key='[SENDKEY]'):
    try:
        post_data = urllib.parse.urlencode({'text': text, 'desp': desp}).encode('utf-8')
        url = f'https://sctapi.ftqq.com/{key}.send'
        req = urllib.request.Request(url, data=post_data, method='POST')
        with urllib.request.urlopen(req) as response:
            result = response.read().decode('utf-8')
        return result
    except Exception as e:
        logger.error(f'推送失败!请检查key:{key}是否有效!原因:"{e}"')


def to_hour_minute(seconds):
    remain_seconds = seconds % (24 * 3600)
    remain_hours = remain_seconds // 3600
    remain_seconds %= 3600
    remain_minutes = remain_seconds // 60
    return remain_hours, remain_minutes, remain_seconds


def task(_schedule_times=None):
    if _schedule_times is None:
        _schedule_times: list = [
            '17:30',
            '20:30',
            '22:30',
            '23:59'
        ]
    today = datetime.datetime.now().date()  # 获取当前的日期
    remain_do_time = []  # 获取所有距离下次任务的剩余时间的列表
    # 创建调度器对象
    scheduler = sched.scheduler(time.time, time.sleep)
    # 遍历每个时间点，将任务安排到调度器中
    for time_str in _schedule_times:
        # 将当前日期与时间点拼接成一个完整的日期时间对象
        scheduled_time = datetime.datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M")
        # 如果时间点已经过去，则加一天
        if scheduled_time < datetime.datetime.now():
            scheduled_time += datetime.timedelta(days=1)
        # 计算距离现在的秒数
        delay = (scheduled_time - datetime.datetime.now()).total_seconds()
        remain_do_time.append(delay)
        # 向调度器中添加任务
    next_do_time = min(remain_do_time)
    scheduler.enter(next_do_time, 1, reduce_price)
    logger.info(
        f'开始执行任务,当前时间:{datetime.datetime.now()} 距离下次执行任务还有%d:%02d:%02d' % (
            to_hour_minute(next_do_time)))
    scheduler.run()


if __name__ == '__main__':
    try:
        record_last_result('')
        reduce_price()
    except Exception as e:
        logger.exception(e)
