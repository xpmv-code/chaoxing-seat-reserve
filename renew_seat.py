# -*- coding: utf-8 -*-
"""
超星图书馆座位续约脚本（续约到闭馆）
登录后从当前预约结束时间起，循环续约后续所有时段，直到闭馆（单次2-4小时）。
9点签到后执行可一次续约全天；12点检查任务再执行时若已续满则自动跳过，实现兜底。
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
    """续约到闭馆：循环续约后续所有时段"""
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

    fid_enc = user_config.get("fidEnc", "e17c5f34de515200")
    renewed = []

    while True:
        # 每次续约后重新获取当前预约（结束后约30分钟内可能移出curReserves，需尽快续）
        seat_reserve = s.get_cur_reserve(roomid, seatid, fid_enc)
        if not seat_reserve:
            if renewed:
                logging.info("续约过程中当前预约消失，停止续约")
            else:
                logging.info("当前没有进行中的预约，无需续约")
                send_bark(config, "续约：当前无进行中的预约")
            return

        reserve_id = seat_reserve.get("id")
        end_ms = seat_reserve.get("endTime", 0)
        end_str = datetime.datetime.fromtimestamp(end_ms / 1000).strftime("%H:%M")

        seg_start, seg_end = next_segment(end_ms, close_time)
        if seg_start >= seg_end:
            # 已到闭馆
            if renewed:
                msg = "、".join(f"{a}-{b}" for a, b in renewed)
                logging.info(f"续约完成，覆盖至 {end_str}")
                send_bark(config, f"续约成功 {msg}（至{end_str}）")
            else:
                logging.info(f"当前预约已到闭馆时间 {end_str}，无需续约")
                send_bark(config, f"续约：已到闭馆时间 {end_str}")
            return

        logging.info(f"当前预约 reserveId={reserve_id} 结束于 {end_str}，续约 {seg_start}-{seg_end}")
        new_id = s.renewal([seg_start, seg_end], roomid, seatid, reserve_id)
        if not new_id:
            err = getattr(s, 'last_error', None) or "可能未签到或风控"
            logging.error(f"续约失败 - 座位{seatid} {seg_start}-{seg_end}: {err}")
            if renewed:
                send_bark(config, f"续约部分完成 {renewed}，下一段{seg_start}-{seg_end}失败：{err}")
            else:
                send_bark(config, f"续约失败 - 座位{seatid} {seg_start}-{seg_end}：{err}")
            return
        renewed.append((seg_start, seg_end))
        time.sleep(2)  # 每次续约间隔，避免过频触发风控


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
