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
import datetime

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
    # end 早于 start 有两种情况：
    #  1) 跨午夜窗口：晚间(>12:00)启动、次日凌晨 end 截止
    #  2) 启动已晚于 end（如 00:05 后才启动），此时窗口已过应立即结束，避免无限循环
    if start_seconds > 12 * 3600:  # 启动晚于中午12点，判定为跨午夜
        return now_seconds >= start_seconds or now_seconds < end_seconds
    # 凌晨启动但已超过截止时间，说明抢座窗口已过
    return False


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

def wait_until(target_hms):
    """等待到当天目标时间 HH:MM，已过则不等待（签到窗口为预约前后20分钟）"""
    now = datetime.datetime.now()
    h, m = map(int, target_hms.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        logging.info(f"目标时间 {target_hms} 已过，直接执行")
        return
    wait_s = (target - now).total_seconds()
    logging.info(f"等待到 {target_hms}（约 {wait_s/3600:.1f} 小时后）")
    time.sleep(wait_s)


def main_with_renewal(users, action=False):
    """持续运行模式：预约第一段 → 等待第一段开始时间签到(仅一次) → 连续续约到结束时段"""
    current_time = get_current_time(action)
    current_dayofweek = get_current_dayofweek(action)
    logging.info(f"持续运行模式(签到续约)启动 {current_time} ({current_dayofweek})")

    if action:
        usernames, passwords = get_user_credentials(action)

    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()

        if daysofweek and current_dayofweek not in daysofweek:
            logging.info("今天没有预订!")
            continue

        if action:
            username, password = usernames.split(',')[index], passwords.split(',')[index]

        if isinstance(seatid, str):
            seatid = [seatid]
        seat = seatid[0]

        s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT,
                    enable_slider=ENABLE_SLIDER, reserve_next_day=RESERVE_NEXT_DAY)
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({'Host': 'office.chaoxing.com'})

        # 切分时段（单次上限4小时，最短2小时，30分钟对齐）
        segments = s._split_times(times[0], times[1])
        logging.info(f"总时段 {times[0]}-{times[1]} 切分为 {len(segments)} 段: {segments}")

        # === 预约第一段 ===
        first_start, first_end = segments[0]
        logging.info(f"=== 预约第一段: {first_start}-{first_end} ===")
        token, value = s._get_page_token(s.url.format(roomid, seat), require_value=True)
        suc = s.get_submit(
            s.submit_url, times=[first_start, first_end],
            token=token, roomid=roomid, seatid=seat,
            captcha="", action=action, value=value,
        )
        if not suc:
            logging.error("第一段预约失败，终止")
            return
        reserve_id = s.last_reserve_id
        logging.info(f"第一段预约成功 reserveId={reserve_id}")

        # === 仅在第一段开始时间签到一次，之后连续续约无需再签到 ===
        first_sign_time = segments[0][0]
        logging.info(f"=== 等待签到时间 {first_sign_time}（全天仅签到一次）===")
        wait_until(first_sign_time)
        if not s.sign(reserve_id):
            logging.error("签到失败，无法进行后续续约")
            return

        # 连续续约后续段（每次续约后页面自动刷新 submit_enc，无需再签到）
        for i in range(1, len(segments)):
            seg_start, seg_end = segments[i]
            logging.info(f"=== 续约 {seg_start}-{seg_end} ===")
            new_id = s.renewal([seg_start, seg_end], roomid, seat, reserve_id, action)
            if new_id:
                reserve_id = new_id
            else:
                logging.error(f"续约失败 {seg_start}-{seg_end}，终止后续续约")
                break

            time.sleep(2)

        # 发送 Bark 通知
        if s.success_results:
            s.send_bark_notification()

    logging.info("持续运行模式结束")


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
    parser.add_argument('-m', '--method', default="reserve", choices=["reserve", "debug", "room", "renewal"], help='execution method: reserve=抢座循环, debug=单次测试, renewal=预约+签到续约持续运行')
    parser.add_argument('-a', '--action', action="store_true", help='enable GitHub Action mode')
    args = parser.parse_args()
    
    # 执行对应的方法
    func_dict = {"reserve": main, "debug": debug, "room": get_roomid, "renewal": main_with_renewal}
    with open(args.user, "r+", encoding="utf-8") as data:
        usersdata = json.load(data)["reserve"]
    func_dict[args.method](usersdata, args.action)
