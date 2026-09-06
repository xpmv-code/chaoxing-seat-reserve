# -*- coding: utf-8 -*-
"""
超星图书馆座位退座脚本
每天指定时间自动退座（取消当前预约）
"""
import json
import time
import argparse
import logging
import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from utils import reserve


def cancel_seat(config_path="config.json"):
    """退座：取消当前进行中的预约"""
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    today = time.strftime("%A")
    user_config = None
    for u in config["reserve"]:
        if not u.get("daysofweek") or today in u["daysofweek"]:
            user_config = u
            break

    if not user_config:
        logging.info(f"今天({today})没有预约配置，无需退座")
        return

    username = user_config["username"]
    password = user_config["password"]
    roomid = user_config["roomid"]
    seatid = user_config["seatid"][0] if isinstance(user_config["seatid"], list) else user_config["seatid"]
    seat_num = int(seatid)  # seatNum 参数用数字，如 27 而非 027

    logging.info(f"退座任务启动 - 账号:{username} 房间:{roomid} 座位:{seatid}")

    # 登录
    s = reserve()
    s.get_login_status()
    login_ok, msg = s.login(username, password)
    if not login_ok:
        logging.error(f"登录失败: {msg}")
        send_bark(config, f"退座失败：登录失败 - {msg}")
        return
    s.requests.headers.update({'Host': 'office.chaoxing.com'})

    # 获取当前预约信息
    info_url = f"https://office.chaoxing.com/data/apps/seat/reserve/info?id={roomid}&seatNum={seat_num}"
    try:
        r = s.requests.get(info_url, verify=False, timeout=15)
        data = r.json()
    except Exception as e:
        logging.error(f"获取预约信息失败: {str(e)[:100]}")
        send_bark(config, f"退座失败：获取预约信息异常")
        return

    seat_reserve = data.get("data", {}).get("seatReserve")
    if not seat_reserve:
        logging.info("当前没有进行中的预约，无需退座")
        send_bark(config, "退座：当前无进行中的预约")
        return

    reserve_id = seat_reserve.get("id")
    status = seat_reserve.get("status")
    status_text = "已签到" if status == 1 else "未签到"
    start_ts = seat_reserve.get("startTime", 0) / 1000
    end_ts = seat_reserve.get("endTime", 0) / 1000
    start_str = datetime.datetime.fromtimestamp(start_ts).strftime("%H:%M")
    end_str = datetime.datetime.fromtimestamp(end_ts).strftime("%H:%M")

    logging.info(f"找到当前预约 - reserveId:{reserve_id} 状态:{status_text} 时段:{start_str}-{end_str}")

    # 根据预约状态选择退座方式
    # status=0 未签到 → cancel 接口；status=1/3/5 已签到 → signback 接口
    if status == 0:
        cancel_url = "https://office.chaoxing.com/data/apps/seat/cancel"
        action_text = "取消预约"
    else:
        cancel_url = "https://office.chaoxing.com/data/apps/seat/signback"
        action_text = "退座"

    try:
        r = s.requests.post(cancel_url, params={"id": reserve_id}, verify=False, timeout=15)
        result = r.json()
    except Exception as e:
        logging.error(f"{action_text}请求失败: {str(e)[:100]}")
        send_bark(config, f"{action_text}失败：请求异常")
        return

    if result.get("success"):
        logging.info(f"{action_text}成功 - reserveId:{reserve_id} 座位:{seatid} {start_str}-{end_str}")
        send_bark(config, f"{action_text}成功 - 座位{seatid} {start_str}-{end_str} 已释放")
    else:
        msg = result.get("msg", "未知错误")
        logging.error(f"{action_text}失败: {msg}")
        send_bark(config, f"{action_text}失败：{msg}")


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
        url = f"{server}/{key}/超星退座/{message}"
        requests.get(url, timeout=10)
    except Exception as e:
        logging.warning(f"Bark 推送失败: {str(e)[:50]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Chao Xing seat cancel')
    parser.add_argument('-u', '--user', default='config.json', help='user config file')
    args = parser.parse_args()
    cancel_seat(args.user)
