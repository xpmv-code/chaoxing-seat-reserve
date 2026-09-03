# ChaoXing-Seat-Reservation

超星学习通（超星图书馆）**自动预约座位脚本**：自动登录、在开放预约时刻循环抢座、按场馆规则自动切分时段，预约成功后通过 **Bark** 推送到 iPhone/iPad。

本仓库在原超星抢座脚本基础上重构与适配，默认参数针对**西安体育学院图书馆**（`roomid=14176`）校准；其他学校只需替换 `roomid`、座位号和顶部时间参数即可，详见[适配其他学校](#适配其他学校)。

## 功能特性

- 自动登录学习通（账号密码 AES 加密传输）
- 到点循环抢座，**支持跨午夜运行窗口**（如 23:59 启动、00:05 结束）
- 支持多账号 / 多条目，可分别配置工作日、周末的不同时段
- 支持多个备选座位（按优先级依次尝试）
- 超长时段自动切分：**单段 2~4 小时、30 分钟对齐**，尾段不足自动回借
- 预约结果 **Bark 推送**（取代旧版邮件通知）
- 可选滑块验证码识别（默认关闭，需额外安装 OpenCV）
- 登录失败直接打印服务端返回原因，便于排错

## 目录结构

```
.
├── main.py               # 入口：参数、主循环、命令行解析
├── config.example.json   # 配置模板（复制为 config.json 使用）
├── requirements.txt      # 依赖清单
├── utils/
│   ├── __init__.py       # GitHub Action 模式下读取环境变量账号
│   ├── reserve.py        # 核心：登录、取 token、提交预约、时段切分、Bark 推送
│   └── encrypt.py        # AES 登录加密与提交参数 MD5 签名
├── chaoxing.bat          # Windows 定时运行（可选，含运行后关机，需自行改路径）
└── img/                  # 抓取 roomid 的教程截图
```

## 快速开始

### 1. 环境要求

- Python 3.8+（开发验证环境为 Python 3.13）
- 建议使用虚拟环境

```bash
git clone https://github.com/xpmv-code/chaoxing-seat-reserve.git
cd chaoxing-seat-reserve

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` 默认只安装运行必需的 `cryptography`、`requests`。
若学校开启了滑块验证，再额外安装并把 `main.py` 的 `ENABLE_SLIDER` 改为 `True`：

```bash
pip install numpy opencv-python
```

### 2. 填写配置

```bash
cp config.example.json config.json
```

编辑 `config.json`（**该文件已被 `.gitignore` 忽略，不会被提交，请勿泄露**）：

```json
{
  "reserve": [
    {
      "username": "你的学习通账号",
      "password": "你的学习通密码",
      "time": ["08:00", "22:00"],
      "roomid": "14176",
      "seatid": ["023"],
      "daysofweek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    {
      "username": "你的学习通账号",
      "password": "你的学习通密码",
      "time": ["09:00", "22:00"],
      "roomid": "14176",
      "seatid": ["023", "024", "025"],
      "daysofweek": ["Saturday", "Sunday"]
    }
  ],
  "bark": {
    "server": "https://api.day.app",
    "key": "你的Bark设备Key"
  }
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `username` / `password` | 学习通登录账号、密码 |
| `time` | 预约起止时间 `[开始, 结束]`，超过单次时长上限会自动切段 |
| `roomid` | 图书馆 / 区域 ID，获取方式见下 |
| `seatid` | 座位号列表，**必须用 0 补齐 3 位**（6 号写 `"006"`）；可填多个作为备选，按顺序尝试 |
| `daysofweek` | 生效星期（英文）；留空 `[]` 表示每天生效。可用多条记录区分工作日 / 周末时段 |
| `bark.server` | Bark 服务器，官方为 `https://api.day.app`，自建服务器填自己的域名 |
| `bark.key` | Bark App 内的设备 Key |

### 3. 获取 roomid 与座位号

在学习通进入"预约图书馆列表"时**断开网络**，点击目标图书馆的「选座」按钮，页面报错后点右上角菜单「复制链接」，得到形如：

```
https://office.chaoxing.com/front/apps/seat/select?id=14176&day=2026-09-04&...
```

其中 `id=14176` 即 `roomid`；座位号在选座页面查看，记得补齐 3 位。

### 4. 运行

```bash
# 调试模式：立即执行一次，用于验证账号、座位和配置是否正确
python main.py -m debug

# 正式模式：从启动时刻循环尝试，直到 main.py 中 ENDTIME 或全部成功
python main.py

# 指定其他配置文件
python main.py -u myconfig.json
```

命令行参数：

| 参数 | 取值 | 说明 |
|---|---|---|
| `-u, --user` | 路径 | 配置文件，默认同目录 `config.json` |
| `-m, --method` | `reserve` / `debug` / `room` | 正式抢座 / 调试一次 / 交互式查询房间 |
| `-a, --action` | 开关 | GitHub Action 模式（账号从环境变量读取，见下文） |

## 运行参数（main.py 顶部）

```python
SLEEPTIME = 1            # 每次尝试间隔（秒），整点抢座建议 1s 左右，不建议过小
ENDTIME = "00:05:00"     # 停止尝试的时刻（学校 0 点放座，抢到 00:05）
ENABLE_SLIDER = False    # 是否启用滑块验证
MAX_ATTEMPT = 2          # 单个时段每轮的最大尝试次数（外层仍会循环到 ENDTIME）
RESERVE_NEXT_DAY = False # True=约明天，False=约当天（按学校开放规则设置）
```

> 正式模式支持**跨午夜窗口**：当 `ENDTIME` 早于启动时刻时自动视为次日，例如 23:59 启动会一直尝试跨过 0 点到 00:05；运行过程中星期切换也会实时重新匹配条目。

## Bark 推送配置

1. iPhone/iPad 安装 Bark App，打开后复制自己的推送 URL，形如 `https://api.day.app/xxxxxxxx/`，其中 `xxxxxxxx` 即 `key`；
2. 填入 `config.json` 的 `bark.key`；
3. 预约成功后会收到标题为「超星图书馆预约成功（共 N 条）」的推送，正文逐条列出房间、座位、日期与时段，并归入「超星抢座」分组；
4. 使用自建 Bark 服务器时把 `bark.server` 改为自己的域名即可。推送失败只记录日志，不影响抢座主流程。

## 部署：定时自动抢座

脚本需要在学校**开放预约的时刻保持运行**。云服务器 7×24 在线，是最稳妥的方案。

### Linux 云服务器（推荐）

> 关键：脚本按服务器**本地时间**判断开放时刻，务必先把时区设为北京时间，否则会错位 8 小时。

```bash
# 1) 设置时区为北京时间
sudo timedatectl set-timezone Asia/Shanghai
date    # 确认输出 CST 时间

# 2) 拉代码、建环境、装依赖、放好 config.json（过程同上）

# 3) 添加定时任务：每天 23:59 自动启动，跨过 0 点抢座
crontab -e
```

写入（路径改成你的实际路径）：

```cron
59 23 * * * cd /opt/chaoxing-seat-reserve && /opt/chaoxing-seat-reserve/venv/bin/python main.py >> run.log 2>&1
```

### macOS / Windows 本地

- macOS：用 `crontab -e`（同上）或「日历/launchd」在 23:59 唤醒运行，注意电脑不能休眠；
- Windows：用「任务计划程序」定时执行，或参考 `chaoxing.bat`（其中路径为占位符，需自行修改）。

### GitHub Action（需自备 workflow）

代码保留了 `-a` 模式：账号从仓库 Secrets `USERNAMES`、`PASSWORDS` 读取（多账号用英文逗号分隔），并自动按 UTC+8 修正日期。仓库默认未附带 workflow 文件，需要自行在 `.github/workflows/` 下编写定时工作流后使用。

## 适配其他学校

不同学校的开放规则不同，先查清规则再改参数。登录后可请求场馆配置接口（把 `ROOMID` 换成目标区域）：

```
https://office.chaoxing.com/data/apps/seat/room/info?id=ROOMID
```

重点关注 `seatConfig`：

- `reserveBeforeDay / reserveBeforeTime`：最早可预约时间（判断是当天放座还是提前一天）
- `reserveDuration`、`minReserveDuration`：单次预约时长上 / 下限，据此修改 `utils/reserve.py` 中 `_split_times()` 的 `max_hours / min_hours`
- `commonTimeConfig` / `seatSpecialTime`：每天开闭馆时间，据此设置 `time` 与工作日 / 周末条目
- `securityVerify`：为 1 时需要滑块验证（安装 numpy、opencv-python 并开启 `ENABLE_SLIDER`）

据此调整 `main.py` 顶部的 `RESERVE_NEXT_DAY`、`ENDTIME` 与 `config.json` 即可。

## 常见问题

- **「当前区域未到开放预约时间」**：还没到该区域放座时间，属于正常现象，正式模式会在开放后自动抢到；请先确认学校几点放座并相应设置 `ENDTIME`。
- **「该时间段已过，不可预约」**：预约的开始时间已经过去，请约未来时段。
- **「用户名或密码错误」**：先用浏览器打开 `https://passport2.chaoxing.com/mlogin?loginType=1&newversion=true&fid=` 手动验证账号密码；注意是登录密码而非短信验证码，部分学校需用学号登录。
- **「当前人数过多，请等待 5 分钟后尝试」**：多为超星接口变更导致请求参数失效，请关注上游更新。
- **其他字典形式报错**：核对账号密码、`roomid`、`seatid`（是否补齐 3 位）是否正确。
- 手动排错顺序：①浏览器能正常登录 → ②打开 `https://office.chaoxing.com/front/third/apps/seat/code?id=房间id&seatNum=座位id` 能看到时间表 → ③尝试预约看是否弹出验证。

## 免责声明

本脚本仅供学习与个人合理使用，请遵守学校图书馆座位管理规定，勿用于商业用途或恶意抢占；因使用本脚本产生的一切后果由使用者自行承担。

## License 与致谢

基于 [Apache License 2.0](LICENSE) 开源，使用时请保留原始版权与许可声明。

原始项目：

- Gitee：https://gitee.com/lcz2000/ChaoXingLibrarySeatReservation
- GitHub 衍生参考：https://github.com/Holmes2718/JSU-Book_a_Seat_on_Superstar_Learning_Platform
