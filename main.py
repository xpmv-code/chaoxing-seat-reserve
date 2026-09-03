# -*- coding: utf-8 -*-
"""
超星图书馆座位预约工具
自动登录并预约指定的座位
"""
import json
import time
import argparse
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from utils import reserve, get_user_credentials

# 时间获取函数（支持时区偏移）
get_current_time = lambda action: time.strftime("%H:%M:%S", time.localtime(time.time() + 8*3600)) if action else time.strftime("%H:%M:%S", time.localtime(time.time()))
get_current_dayofweek = lambda action: time.strftime("%A", time.localtime(time.time() + 8*3600)) if action else time.strftime("%A", time.localtime(time.time()))

# === 配置参数（已按西安体育学院图书馆 roomid=14176 的规则校准）===
SLEEPTIME = 1           # 每次尝试的间隔时间（秒）：该校0点放座，间隔要短
ENDTIME = "00:05:00"    # 停止尝试的时间（0点开放，抢到0点05分）
ENABLE_SLIDER = False   # 是否启用滑块验证（该校 securityVerify=0，无需滑块）
MAX_ATTEMPT = 2         # 单时段单次遍历的最大尝试次数（外层仍会循环到ENDTIME）
RESERVE_NEXT_DAY = False # 该校当天0点开放当天座位，因此约当天而非次日



def login_and_reserve(users, usernames, passwords, action, success_list=None):
    """登录并预约座位"""
    logging.info(f"全局设置: 睡眠时间={SLEEPTIME}s 结束时间={ENDTIME} 滑块验证={ENABLE_SLIDER} 预约次日={RESERVE_NEXT_DAY}")
    
    if action and len(usernames.split(",")) != len(users):
        raise Exception("用户号应与配置号匹配")
    
    if success_list is None:
        success_list = [False] * len(users)
    
    current_dayofweek = get_current_dayofweek(action)
    reserve_instances = []  # 保存所有的 reserve 实例

    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        
        # 检查今天是否需要预约
        if current_dayofweek not in daysofweek and daysofweek:
            logging.info("今天没有预订!")
            continue
        
        # 跳过已成功的预约
        if success_list[index]:
            continue
        
        if action:
            username, password = usernames.split(',')[index], passwords.split(',')[index]
        
        logging.info(f"开始预约: {username} - {times} - {seatid}")
        
        # 创建预约实例并预约
        s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER, reserve_next_day=RESERVE_NEXT_DAY)
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({'Host': 'office.chaoxing.com'})
        suc = s.submit(times, roomid, seatid, action)
        success_list[index] = suc
        reserve_instances.append(s)
    
    # 统一发送邮件（包含所有成功的预约）
    if reserve_instances:
        for s in reserve_instances:
            if s.success_results:
                s.send_bark_notification()
                break  # 只发送一次（合并所有结果）
    
    return success_list


def _hms_to_seconds(hms):
    """HH:MM:SS 转换为当天经过的秒数"""
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s


def _in_running_window(now_str, start_seconds, end_seconds):
    """判断当前时间是否仍在抢座窗口内，支持跨午夜（如23:59启动、00:05结束）"""
    now_seconds = _hms_to_seconds(now_str)
    if end_seconds > start_seconds:
        return now_seconds < end_seconds
    # 结束时刻早于启动时刻，说明结束点在次日
    return now_seconds >= start_seconds or now_seconds < end_seconds


def main(users, action=False):
    """主预约循环"""
    current_time = get_current_time(action)
    start_seconds = _hms_to_seconds(current_time)
    end_seconds = _hms_to_seconds(ENDTIME)
    logging.info(f"开始时间 {current_time} ({'action' if action else 'preview'})，窗口截止 {ENDTIME}")

    attempt_times = 0
    success_list = None
    usernames, passwords = None, None

    if action:
        usernames, passwords = get_user_credentials(action)

    # 主循环：不断尝试预约直到超出窗口或全部成功
    while _in_running_window(current_time, start_seconds, end_seconds):
        attempt_times += 1
        # 每轮重新计算星期，兼容23:5x启动、跨午夜后星期切换
        current_dayofweek = get_current_dayofweek(action)
        today_reservation_num = sum(
            1 for d in users if not d.get('daysofweek') or current_dayofweek in d.get('daysofweek')
        )

        success_list = login_and_reserve(users, usernames, passwords, action, success_list)

        logging.info(f"尝试 #{attempt_times} | 当前时间 {current_time}({current_dayofweek}) | 成功 {sum(success_list)}/{today_reservation_num}")

        # 检查是否全部预约成功
        if today_reservation_num > 0 and sum(success_list) == today_reservation_num:
            logging.info("已成功预订所有座位!")
            return

        current_time = get_current_time(action)


def debug(users, action=False):
    """调试模式：单次预约并发送邮件"""
    logging.info(f"调试模式启动 ({'action' if action else 'preview'})")
    logging.info(f"配置: 睡眠={SLEEPTIME}s 滑块={ENABLE_SLIDER} 次日={RESERVE_NEXT_DAY}")
    
    if action:
        usernames, passwords = get_user_credentials(action)
    
    current_dayofweek = get_current_dayofweek(action)
    
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        
        # 座位ID转为列表（若为字符串）
        if isinstance(seatid, str):
            seatid = [seatid]
        
        # 检查今天是否需要预约
        if current_dayofweek not in daysofweek:
            logging.info("今天没有预订")
            continue
        
        if action:
            username, password = usernames.split(',')[index], passwords.split(',')[index]
        
        logging.info(f"预约: {username} - {times} - {seatid}")
        
        # 执行预约
        s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER, reserve_next_day=RESERVE_NEXT_DAY)
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({'Host': 'office.chaoxing.com'})
        suc = s.submit(times, roomid, seatid, action)
        
        # 发送邮件并返回
        if suc and s.success_results:
            s.send_bark_notification()
        return

def get_roomid(args1, args2):
    """获取房间ID（用于探测）"""
    username = input("请输入用户名: ")
    password = input("请输入密码: ")
    
    s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER, reserve_next_day=RESERVE_NEXT_DAY)
    s.get_login_status()
    s.login(username=username, password=password)
    s.requests.headers.update({'Host': 'office.chaoxing.com'})
    
    deptid_enc = input("请输入deptIdEnc: ")
    s.roomid(deptid_enc)


if __name__ == "__main__":
    # 读取命令行参数
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    parser = argparse.ArgumentParser(prog='Chao Xing seat auto reserve')
    parser.add_argument('-u', '--user', default=config_path, help='user config file')
    parser.add_argument('-m', '--method', default="reserve", choices=["reserve", "debug", "room"], help='execution method')
    parser.add_argument('-a', '--action', action="store_true", help='enable GitHub Action mode')
    args = parser.parse_args()
    
    # 执行对应的方法
    func_dict = {"reserve": main, "debug": debug, "room": get_roomid}
    with open(args.user, "r+", encoding="utf-8") as data:
        usersdata = json.load(data)["reserve"]
    func_dict[args.method](usersdata, args.action)
