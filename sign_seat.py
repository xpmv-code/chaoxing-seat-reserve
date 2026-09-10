# -*- coding: utf-8 -*-
"""
超星图书馆座位签到脚本（分段定时任务用）
登录后获取当前预约的 reserveId，调用签到接口签到（预约前后20分钟内有效）
"""
import json
import time
import argparse
import logging
import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from utils import reserve


def sign_seat(config_path="config.json"):
    """签到：对当前进行中的预约签到"""
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    today = time.strftime("%A")
    user_config = None
    for u in config["reserve"]:
        if not u.get("daysofweek") or today in u["daysofweek"]:
            user_config = u
            break

    if not user_config:
        logging.info(f"今天({today})没有预约配置，无需签到")
        return

    username = user_config["username"]
    password = user_config["password"]
    roomid = user_config["roomid"]
    seatid = user_config["seatid"][0] if isinstance(user_config["seatid"], list) else user_config["seatid"]
    seat_num = int(seatid)

    logging.info(f"签到任务启动 - 账号:{username} 房间:{roomid} 座位:{seatid}")

    s = reserve()
    if not s.get_login_status():
        ok, msg = s.login(username, password)
        if not ok:
            logging.error(f"登录失败: {msg}")
            send_bark(config, "签到失败", f"座位{seatid}：登录失败 - {msg}")
            return
    s.requests.headers.update({'Host': 'office.chaoxing.com'})

    # 获取当前预约信息（用 curReserves 接口）
    fid_enc = user_config.get("fidEnc", "e17c5f34de515200")
    seat_reserve = s.get_cur_reserve(roomid, seatid, fid_enc)
    if not seat_reserve:
        logging.info("当前没有进行中的预约，无需签到")
        send_bark(config, "签到跳过", f"座位{seatid}：无进行中预约")
        return

    reserve_id = seat_reserve.get("id")
    status = seat_reserve.get("status")
    if status == 1:
        logging.info(f"当前预约已签到过（reserveId={reserve_id}），跳过")
        send_bark(config, "签到跳过", f"座位{seatid}：已签到过")
        return

    if s.sign(reserve_id):
        send_bark(config, "签到成功", f"座位{seatid}")
    else:
        send_bark(config, "签到失败", f"座位{seatid}")


def send_bark(config, title, body, group="超星签到"):
    """通过 Bark 推送通知（统一结构化格式）"""
    bark = config.get("bark", {})
    server = bark.get("server", "https://api.day.app").rstrip("/")
    key = bark.get("key", "")
    if not key:
        logging.warning("未配置 Bark key，跳过推送")
        return
    try:
        import requests
        requests.post(f"{server}/{key}", json={
            "title": title,
            "body": body,
            "group": group,
        }, timeout=10)
    except Exception as e:
        logging.warning(f"Bark 推送失败: {str(e)[:50]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Chao Xing seat sign')
    parser.add_argument('-u', '--user', default='config.json', help='user config file')
    args = parser.parse_args()
    sign_seat(args.user)
