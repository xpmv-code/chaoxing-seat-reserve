# -*- coding: utf-8 -*-
"""
超星图书馆座位续约脚本（分段定时任务用）
登录后获取当前预约，从结束时间自动续约下一段（单次最多4小时，不超过闭馆时间）
"""
import json
import time
import argparse
import logging
import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from utils import reserve


def next_segment(end_time_ms, close_time):
    """计算下一段：从当前预约结束时间起，最多4小时，不超过闭馆时间"""
    end_dt = datetime.datetime.fromtimestamp(end_time_ms / 1000)
    start = end_dt.strftime("%H:%M")
    # 起始对齐到半小时
    start_dt = end_dt.replace(minute=0, second=0, microsecond=0)
    if end_dt.minute >= 30:
        start_dt = start_dt.replace(minute=30)
    start = start_dt.strftime("%H:%M")

    close_h, close_m = map(int, close_time.split(":"))
    close_dt = end_dt.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    end_candidate = start_dt + datetime.timedelta(hours=4)
    end_dt2 = min(end_candidate, close_dt)
    end = end_dt2.strftime("%H:%M")
    return start, end


def renew_seat(config_path="config.json"):
    """续约：从当前预约结束时间续约下一段"""
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    today = time.strftime("%A")
    user_config = None
    for u in config["reserve"]:
        if not u.get("daysofweek") or today in u["daysofweek"]:
            user_config = u
            break

    if not user_config:
        logging.info(f"今天({today})没有预约配置，无需续约")
        return

    username = user_config["username"]
    password = user_config["password"]
    roomid = user_config["roomid"]
    seatid = user_config["seatid"][0] if isinstance(user_config["seatid"], list) else user_config["seatid"]
    seat_num = int(seatid)
    close_time = user_config["time"][1]  # 当天闭馆时间

    logging.info(f"续约任务启动 - 账号:{username} 房间:{roomid} 座位:{seatid} 闭馆:{close_time}")

    s = reserve()
    if not s.get_login_status():
        ok, msg = s.login(username, password)
        if not ok:
            logging.error(f"登录失败: {msg}")
            send_bark(config, f"续约失败：登录失败 - {msg}")
            return
    s.requests.headers.update({'Host': 'office.chaoxing.com'})

    # 获取当前预约信息
    info_url = f"https://office.chaoxing.com/data/apps/seat/reserve/info?id={roomid}&seatNum={seat_num}"
    try:
        r = s.requests.get(info_url, verify=False, timeout=15)
        data = r.json()
    except Exception as e:
        logging.error(f"获取预约信息失败: {str(e)[:100]}")
        send_bark(config, "续约失败：获取预约信息异常")
        return

    seat_reserve = data.get("data", {}).get("seatReserve")
    if not seat_reserve:
        logging.info("当前没有进行中的预约，无需续约")
        send_bark(config, "续约：当前无进行中的预约")
        return

    reserve_id = seat_reserve.get("id")
    end_ms = seat_reserve.get("endTime", 0)
    end_str = datetime.datetime.fromtimestamp(end_ms / 1000).strftime("%H:%M")

    # 计算下一段
    seg_start, seg_end = next_segment(end_ms, close_time)
    if seg_start >= seg_end:
        logging.info(f"当前预约已到闭馆时间 {end_str}，无需续约")
        send_bark(config, f"续约：已到闭馆时间 {end_str}")
        return

    logging.info(f"当前预约 reserveId={reserve_id} 结束于 {end_str}，续约 {seg_start}-{seg_end}")

    # 续约（需签到状态，签到后页面才有 submit_enc）
    new_id = s.renewal([seg_start, seg_end], roomid, seatid, reserve_id)
    if new_id:
        send_bark(config, f"续约成功 - 座位{seatid} {seg_start}-{seg_end}")
    else:
        send_bark(config, f"续约失败 - 座位{seatid} {seg_start}-{seg_end}，可能未签到")


def send_bark(config, message):
    """通过 Bark 推送通知"""
    bark = config.get("bark", {})
    server = bark.get("server", "https://api.day.app")
    key = bark.get("key", "")
    if not key:
        logging.warning("未配置 Bark key，跳过推送")
        return
    try:
        import requests
        url = f"{server}/{key}/超星续约/{message}"
        requests.get(url, timeout=10)
    except Exception as e:
        logging.warning(f"Bark 推送失败: {str(e)[:50]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Chao Xing seat renew')
    parser.add_argument('-u', '--user', default='config.json', help='user config file')
    args = parser.parse_args()
    renew_seat(args.user)
