# ChaoXingLibrarySeatReservation
超星图书馆座位预约脚本

## 说明
本项目是基于原有的超星图书馆座位预约项目进行修改与整理。本项目采用 MIT License 开源许可证。

当前版本已适配**西安体育学院图书馆**（roomid=14176），支持 Bark 推送通知，并新增**签到后续约**功能，可实现从开馆到闭馆的全时段自动预约。

## 功能特性

- **自动登录预约**：0点开放后自动抢约当天座位
- **签到续约**：预约第一段后，到签到时间自动签到，随后连续续约所有后续时段（仅需签到一次）
- **时段自动切片**：按学校规则（单次2-4小时）自动切分全天时段
- **Bark 推送**：预约/续约成功后通过 Bark 推送到 iPhone/iPad
- **多用户支持**：支持多个账号同时预约

## 如何使用

> 为了安全，建议将你的真实配置保存在本地的 config.json 中，不要直接提交到 GitHub。仓库中提供了一个示例配置文件 config.example.json，可作为参考。

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

其中的`id=5483`的5483即为对应图书馆的id，座位号联网后自己挑选即可（注意用0补全至3位数，例如6号座位填006）。

### 3、配置 config.json

复制示例配置并修改：

```bash
cp config.example.json config.json
```

编辑 config.json，填写账号、座位、时段等信息（详见下方 config 配置说明）。

### 4、运行

```bash
# 抢座循环模式（0点启动，持续尝试到 ENDTIME）
python main.py -u config.json

# 调试模式（单次预约，立即执行）
python main.py -u config.json -m debug

# 签到续约持续运行模式（推荐：预约第一段→签到→连续续约到闭馆）
python main.py -u config.json -m renewal
```

**推荐使用 `-m renewal` 模式**：0点预约第一段4小时，到开馆时间自动签到一次，随后连续续约所有后续时段直到闭馆，无需人工干预。

### 5、定时任务

Linux 下使用 crontab：

```bash
crontab -e
# 每天0点执行签到续约模式
0 0 * * * cd /path/to/chaoxing-seat-reserve && python main.py -u config.json -m renewal
```

Windows 下使用任务计划程序，设置每天0点触发。

## 签到续约模式说明

西安体育学院图书馆规则：
- 单次预约上限4小时，最短2小时
- 预约开始时间前后20分钟内可扫码签到，未签到视为违约
- 签到后可连续续约后续时段，无需再次签到
- 工作日开馆 08:00-22:00，周末 09:00-22:00

`renewal` 模式运行流程（以周末为例）：

```
00:00  预约第一段 09:00-13:00
09:00  自动签到（仅一次）
       续约 13:00-17:00
       续约 17:00-20:00
       续约 20:00-22:00
```

时段自动切片结果（均在2-4小时区间）：
- 工作日 08:00-22:00 → 08-12、12-16、16-20、20-22
- 周末 09:00-22:00 → 09-13、13-17、17-20、20-22

## config 配置

```json
{
  "reserve": [
    {
      "username": "XXXXXXXX",
      "password": "XXXXXXXX",
      "time": ["08:00", "22:00"],
      "roomid": "14176",
      "seatid": ["023"],
      "daysofweek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    {
      "username": "XXXXXXXX",
      "password": "XXXXXXXX",
      "time": ["09:00", "22:00"],
      "roomid": "14176",
      "seatid": ["023"],
      "daysofweek": ["Saturday", "Sunday"]
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
- `roomid`：图书馆ID（西安体育学院为 14176）
- `seatid`：座位号列表，用0补全至3位数
- `daysofweek`：预约的星期，留空则每天都约
- `bark.server` / `bark.key`：Bark 推送配置，用于接收预约成功通知

## 高级设置

在 main.py 中有以下参数可调整：

```python
SLEEPTIME = 1           # 每次抢座间隔（秒）
ENDTIME = "00:05:00"    # 抢座窗口截止时间
ENABLE_SLIDER = False    # 是否启用滑块验证
MAX_ATTEMPT = 2          # 单时段最大尝试次数
RESERVE_NEXT_DAY = False # 是否预约次日（西安体院当天0点放当天座位）
```

## 常见问题

- **"本周违约次数已达上限"**：账号因未签到违约次数超限，需等待下周重置或更换账号
- **"当前人数过多，请等待5分钟后尝试"**：请求过于频繁，适当增大 SLEEPTIME
- **登录失败（403）**：学习通登录服务对频繁请求触发IP风控，等待数小时后自动解除
- **预约失败**：检查用户名密码、roomid、seatid 是否正确，以及当天是否已有预约

## 致谢

源项目：https://gitee.com/lcz2000/ChaoXingLibrarySeatReservation
