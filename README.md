# ChaoXingLibrarySeatReservation

超星图书馆座位预约脚本（已适配西安体育学院）

## 说明

本项目基于原有的超星图书馆座位预约项目进行修改与整理，采用 **GNU General Public License v2.0 (GPL v2)** 开源许可证。

当前版本适配**西安体育学院图书馆**（roomid=14176），支持 Bark 推送、签到后续约、定时退座、登录态持久化，可实现从开馆到闭馆的全时段自动预约与退座。

## 功能特性

- **自动抢座**：每天 0 点开放后自动抢约当天第一段座位
- **自动签到**：预约开始前后 20 分钟内自动扫码签到（未签视为违约）
- **连续续约**：签到一次后自动连续续约所有后续时段，直到闭馆
- **时段自动切片**：按学校规则（单次 2-4 小时）自动切分全天时段
- **定时退座**：闭馆后自动退座，释放座位
- **登录态持久化**：登录成功后将 cookie 保存到本地 `cookies.json`，后续任务直接复用，避免频繁登录触发风控
- **Bark 推送**：预约/签到/续约/退座结果通过 Bark 实时推送到 iPhone/iPad
- **多用户支持**：支持多个账号同时预约（工作日/周末可配置不同时段）

## 学校规则（西安体育学院）

- 每天最初只能预约 4 小时
- 单次预约或续约：至少 2 小时，至多 4 小时
- 预约开始前后 20 分钟内可扫码签到，未签到视为违约
- 签到一次后，后续时段可连续续约，无需再次签到
- 工作日 08:00-22:00，周末 09:00-22:00

时段自动切片结果：

| 类型 | 时段切片 |
|---|---|
| 工作日 | 08:00-12:00、12:00-16:00、16:00-20:00、20:00-22:00 |
| 周末 | 09:00-13:00、13:00-17:00、17:00-20:00、20:00-22:00 |

## 如何使用

> 为了安全，建议将你的真实配置保存在本地的 config.json 中，不要直接提交到 GitHub。仓库中提供示例配置文件 config.example.json。

### 1、安装依赖

```bash
pip install cryptography requests
```

如果有滑块验证，则需要额外安装 numpy 和 opencv-python：

```bash
pip install numpy opencv-python
```

### 2、获取 roomid 和 seatid

在进入预约图书馆列表界面时断开网络，点击你想预约的图书馆的`选座`按钮，会提示网页无法打开，此时点击`右上角的三条杠`，选择`复制链接`，会得到类似这样的链接：

> https://office.chaoxing.com/front/apps/seat/select?id=5483&day=2023-10-12&backLevel=2&pageToken=0f46f3acc7be4c60862cb9815870ddfd

其中的`id=5483`的 5483 即为对应图书馆的 id。座位号联网后自己挑选即可（注意用 0 补全至 3 位数，例如 6 号座位填 006）。

**fidEnc 获取方式**：访问 `https://office.chaoxing.com/front/apps/seat/select?id={roomid}` 页面，从网络请求中查找 `/data/apps/seat/index?fidEnc=xxx`，xxx 即为 fidEnc（西安体育学院为 `e17c5f34de515200`）。

### 3、配置 config.json

复制示例配置并修改：

```bash
cp config.example.json config.json
```

编辑 config.json，填写账号、座位、时段等信息（详见下方 config 配置说明）。

### 4、运行

```bash
# 预约第一段（0点抢座，单次预约后退出）
python main.py -u config.json -m first

# 签到（预约开始时间执行）
python sign_seat.py -u config.json

# 续约下一段（每段开始时间执行）
python renew_seat.py -u config.json

# 退座（闭馆后执行，自动判断 cancel/signback）
python cancel_seat.py -u config.json

# 持续运行模式（旧版：预约+签到+续约一站式，长进程易被环境终止，不推荐用于定时任务）
python main.py -u config.json -m renewal

# 调试模式（单次预约，立即执行）
python main.py -u config.json -m debug
```

### 5、定时任务（推荐方案）

由于长进程在定时环境中容易被终止，**推荐拆分为多个短时任务**：

```bash
crontab -e

# 抢座第一段（每天0点）
0 0 * * * cd /path/to/chaoxing-seat-reserve && python main.py -u config.json -m first

# 签到（工作日 08:00 / 周末 09:00）
0 8 * * 1-5  cd /path/to/chaoxing-seat-reserve && python sign_seat.py -u config.json
0 9 * * 0,6  cd /path/to/chaoxing-seat-reserve && python sign_seat.py -u config.json

# 续约（工作日 12:00/16:00，周末 13:00/17:00，末段统一 20:00）
0 12 * * 1-5 cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json
0 13 * * 0,6 cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json
0 16 * * 1-5 cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json
0 17 * * 0,6 cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json
0 20 * * *  cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json

# 退座（每天22:00闭馆后）
0 22 * * * cd /path/to/chaoxing-seat-reserve && python cancel_seat.py -u config.json
```

一天完整流程示例（工作日）：

```
00:00  抢座第一段 08:00-12:00
08:00  签到（仅一次）
12:00  续约 12:00-16:00
16:00  续约 16:00-20:00
20:00  续约 20:00-22:00
22:00  退座
```

Windows 下使用任务计划程序，按同样时间点设置触发。

## config 配置

```json
{
  "reserve": [
    {
      "username": "XXXXXXXX",
      "password": "XXXXXXXX",
      "time": ["08:00", "22:00"],
      "roomid": "14176",
      "seatid": ["027"],
      "daysofweek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "fidEnc": "e17c5f34de515200"
    },
    {
      "username": "XXXXXXXX",
      "password": "XXXXXXXX",
      "time": ["09:00", "22:00"],
      "roomid": "14176",
      "seatid": ["027"],
      "daysofweek": ["Saturday", "Sunday"],
      "fidEnc": "e17c5f34de515200"
    }
  ],
  "bark": {
    "server": "https://api.day.app",
    "key": "你的Bark设备Key"
  }
}
```

**字段说明：**
- `username` / `password`：学习通账号密码
- `time`：预约起止时间 `[开始, 结束]`
- `roomid`：图书馆 ID（西安体育学院为 14176）
- `seatid`：座位号列表，用 0 补全至 3 位数
- `daysofweek`：预约的星期，留空则每天都约
- `fidEnc`：图书馆 fid 加密参数（用于查询预约列表，西安体育学院为 `e17c5f34de515200`）
- `bark.server` / `bark.key`：Bark 推送配置，用于接收预约/签到/续约/退座通知

## 登录态与风控

- 脚本登录成功后会将 session cookie 保存到 `cookies.json`（已加入 .gitignore，不会推送 GitHub）
- 各脚本运行时会优先复用 cookie（通过 `/data/apps/seat/index` 接口校验有效性），失效才重新登录
- 若触发学习通 IP 风控（fanyalogin 返回 403），等待数小时自动解除

## 脚本与接口说明

| 脚本 | 作用 | 关键接口 |
|---|---|---|
| `main.py -m first` | 抢约当天第一段 | `POST /data/apps/seat/submit` |
| `sign_seat.py` | 签到一次（已签到自动跳过） | `GET /data/apps/seat/sign?id={reserveId}` |
| `renew_seat.py` | 续约下一段（自动计算 2-4h 切片） | `POST /data/apps/seat/submit`（续约参数） |
| `cancel_seat.py` | 退座（未签到走 cancel，已签到走 signback） | `POST /data/apps/seat/cancel` / `signback` |

预约/续约/退座共用 `GET /data/apps/seat/index?fidEnc=` 的 `curReserves` 获取当前预约记录（含未来时段）。

## 高级设置

在 main.py 中有以下参数可调整：

```python
SLEEPTIME = 1           # 每次抢座间隔（秒）
ENDTIME = "00:05:00"    # 抢座窗口截止时间
ENABLE_SLIDER = False   # 是否启用滑块验证
MAX_ATTEMPT = 2         # 单时段最大尝试次数
RESERVE_NEXT_DAY = False # 是否预约次日（西安体院当天0点放当天座位）
```

## 常见问题

- **"本周违约次数已达上限"**：账号因未签到违约次数超限，需等待下周重置或更换账号
- **"当前人数过多，请等待5分钟后尝试"**：请求过于频繁，适当增大 SLEEPTIME
- **登录失败（403）**：学习通登录服务对频繁请求触发 IP 风控，等待数小时后自动解除
- **预约失败**：检查用户名密码、roomid、seatid 是否正确，以及当天是否已有预约
- **续约失败**：确认第一段已签到（未签到无法续约），或当前时段已到闭馆时间
- **退座提示"当前无进行中的预约"**：可能是预约时段已结束或当天无预约，属正常提示

## 致谢

源项目：https://gitee.com/lcz2000/ChaoXingLibrarySeatReservation
