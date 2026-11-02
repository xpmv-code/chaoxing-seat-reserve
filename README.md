# 超星图书馆座位自动预约（chaoxing-seat-reserve）

超星（学习通）图书馆座位自动预约脚本，已适配**西安体育学院图书馆**（roomid=14176）。它把一天里和座位相关的操作全部自动化：**0 点抢当天第一段座位 → 开始时间自动签到一次 → 签到后连续续约直到闭馆 → 闭馆后自动退座**，每一步的结果通过 Bark 推送到你的手机。

基于 Gitee 源项目二次修改，按 GPL v2 许可证开源（见仓库 `LICENSE` 文件）。

## 目录

- [这是什么](#这是什么)
- [前置条件：它不能做什么](#前置条件它不能做什么)
- [快速开始](#快速开始)
- [脚本清单与用法](#脚本清单与用法)
- [定时任务（cron 示例）](#定时任务cron-示例)
- [配置字段全表](#配置字段全表)
- [常见问题](#常见问题)
- [致谢与许可证](#致谢与许可证)

## 这是什么

配置好并挂上定时任务之后，你每天不需要做任何操作，脚本按下面的节奏跑完全程：

| 时间 | 脚本做的事 | 结果推送 |
|---|---|---|
| 00:00 | 抢当天第一段座位（窗口到 00:05） | 抢座成功 / 抢座失败 |
| 08:00（工作日）/ 09:00（周末） | 自动签到一次 | 签到成功 / 签到失败 / 签到跳过 |
| 09:00（工作日）/ 10:00（周末） | 从当前预约结束时间起自动续约到闭馆 | 续约成功 / 续约失败 / 续约跳过 |
| 12:00 | 兜底检查（已续满则自动跳过） | 续约跳过 |
| 22:00 | 自动退座 | 退座成功 / 退座失败 / 退座跳过 |

与代码切片逻辑一致的时段规则（`utils/reserve.py`）：

- 单次预约或续约至少 2 小时、至多 4 小时，脚本按此把全天时段自动切片（工作日 `08:00-22:00` 切成 08-12、12-16、16-20、20-22；周末 `09:00-22:00` 切成 09-13、13-17、17-20、20-22）
- 签到窗口为预约开始前后 20 分钟，签到一次后后续时段可连续续约，无需再次签到
- 登录成功后 cookie 保存到本地 `cookies.json`，后续任务直接复用，减少重复登录

## 前置条件：它不能做什么

这不是开箱即用的工具，动手前先确认以下几点：

- **你需要一个有效的学习通账号**：脚本用你的账号密码登录并提交预约
- **需要 Python 3**：依赖 `requests`、`cryptography`（Python 2 不行）
- **roomid / seatid / fidEnc 需要你自己确认**：西安体院的值已内置在示例配置里，换学校要自己改
- **不保证一定抢到**：0 点并发取决于平台处理速度，脚本只负责在窗口内按固定间隔重试（间隔 `SLEEPTIME`，窗口截止 `00:05:00`）
- **没有图形界面、不处理人工验证**：滑块验证默认关闭（该校无需滑块）；确需开启要改 `main.py` 的 `ENABLE_SLIDER = True` 并额外安装 `numpy`、`opencv-python`
- **凭证以明文存在本地**：`config.json` 和 `cookies.json` 不要提交到公开仓库（两者都已加入 `.gitignore`）

## 快速开始

### 1. 安装依赖

```bash
pip install cryptography requests
```

只有开启滑块验证（`ENABLE_SLIDER = True`）才需要额外安装：

```bash
pip install numpy opencv-python
```

### 2. 复制并编辑 config.json

```bash
cp config.example.json config.json
```

最小配置示例（完整字段说明见「配置字段全表」）：

```json
{
  "reserve": [
    {
      "username": "你的学习通账号",
      "password": "你的密码",
      "time": ["08:00", "22:00"],
      "roomid": "14176",
      "seatid": ["027"],
      "daysofweek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "fidEnc": "e17c5f34de515200"
    },
    {
      "username": "你的学习通账号",
      "password": "你的密码",
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

逐字段速览：

- `username` / `password`：**必填**。学习通账号密码。
- `time`：**必填**。`["开始", "结束"]`；其中 `time[1]` 会被 `renew_seat.py` 当作当天闭馆时间。
- `roomid`：**必填**。西安体育学院为 `"14176"`。
- `seatid`：**必填**。座位号列表，0 补全至 3 位（如 6 号座填 `"006"`）。
- `daysofweek`：选填。星期英文名列表；留空则每天都预约。
- `fidEnc`：选填。查询当前预约列表的接口参数，西安体院不填也会用默认值 `"e17c5f34de515200"`。
- `bark.key`：选填。Bark 设备 key，不填则跳过所有推送。

### 3. 获取 roomid / seatid / fidEnc

西安体育学院已内置，直接用示例值即可：`roomid=14176`、`fidEnc=e17c5f34de515200`；`seatid` 填你在选座页面上选中的座位号（补足 3 位）。

其他学校：

- `roomid`：运行交互式探测 `python main.py -m room`，按提示输入用户名、密码和 `deptIdEnc`，脚本会调用房间列表接口打印所有房间及 id。`deptIdEnc` 的获取方式代码未提供 [TODO: 需补充]
- `seatid`：图书馆选座页面上的座位编号，0 补全至 3 位
- `fidEnc`：查询当前预约列表用，不填时使用西安体院默认值，换学校需自行确认

### 4. 先跑一次 debug 验证配置

正式交给定时任务前，手动跑一次单次预约测试：

```bash
python main.py -u config.json -m debug
```

`debug` 模式会立即为第一个匹配今天星期的用户提交一次预约（成功后会 Bark 推送）。确认能约上再配定时任务；失败的话日志会打印平台返回的错误原因。

### 5. 配置定时任务

见下一节「定时任务（cron 示例）」。

## 脚本清单与用法

所有脚本都在仓库根目录运行：`sign/renew/cancel` 的 `-u config.json` 是相对当前目录的路径，且 `reserve()` 会从**当前工作目录**的 `config.json` 读取 Bark 配置。

| 脚本 / 模式 | 作用 | 典型执行时机 | 入口命令 |
|---|---|---|---|
| `main.py -m first` | 抢当天第一段座位，成功后退出 | 每天 00:00 | `python main.py -u config.json -m first` |
| `sign_seat.py` | 签到一次；已签到或没有进行中预约则自动跳过 | 预约开始时间（工作日 08:00 / 周末 09:00） | `python sign_seat.py -u config.json` |
| `renew_seat.py` | 从当前预约结束时间起循环续约到闭馆，自动切 2-4 小时段；已覆盖到闭馆则跳过 | 签到后 1 小时 + 中午 12:00 兜底 | `python renew_seat.py -u config.json` |
| `cancel_seat.py` | 退座：未签到走取消接口，已签到走退座接口；没有进行中预约则跳过 | 每天 22:00（闭馆后） | `python cancel_seat.py -u config.json` |
| `main.py -m debug` | 单次预约测试，验证配置 | 手动 | `python main.py -u config.json -m debug` |
| `main.py -m reserve` | 抢座循环：自动切片后预约全天所有时段，循环到 `ENDTIME` 或全部成功 | 手动；不推荐用于定时（长循环） | `python main.py -u config.json` |
| `main.py -m renewal` | 预约第一段 → 等到开始时间签到一次 → 连续续约（长进程） | 不推荐用于定时（长进程易被环境终止） | `python main.py -u config.json -m renewal` |
| `main.py -m room` | 交互式列出房间 id（需要 `deptIdEnc`） | 手动 | `python main.py -m room` |
| `chaoxing.bat`（Windows 启动器） | 按子命令调用上面前 4 个脚本；不带参数显示 1-4 交互菜单；自动切到脚本所在目录并优先用项目 `.venv` 的 Python | Windows 定时任务 / 手动 | `chaoxing.bat first`（或 `sign` / `renew` / `cancel`） |

要点：

- **短时任务优于长进程**：`main.py -m renewal` 把「等待签到 + 连续续约」跑成一个长进程，定时环境里容易被终止；推荐方案是拆成多个短任务（`first` + `sign_seat.py` + `renew_seat.py` + `cancel_seat.py`），每一步都是几十秒内结束的独立进程，见 `main.py` 中 `reserve_first` 的设计注释。
- **续约一次跑完所有后续时段**：`renew_seat.py` 内部循环续约直到闭馆，每次续约间隔 2 秒避免过频触发风控；中午 12:00 再跑一次做兜底，已续满会自动跳过。
- **多用户**：`config.json` 的 `reserve` 数组可配多个账号；`sign/renew/cancel` 三个脚本每天只处理第一个匹配当天星期的用户，`main.py` 则处理所有用户。

## 定时任务（cron 示例）

以下 cron 与推荐方案一一对应。**每行开头的 `cd` 不能省**：`-u config.json` 是相对路径，且脚本要从当前目录的 `config.json` 读取 Bark 配置。

```bash
crontab -e

# 抢座：每天 0 点抢当天第一段
0 0 * * *  cd /path/to/chaoxing-seat-reserve && python main.py -u config.json -m first

# 签到：工作日 08:00 / 周末 09:00（对应 config 里 time[0]）
0 8 * * 1-5  cd /path/to/chaoxing-seat-reserve && python sign_seat.py -u config.json
0 9 * * 0,6  cd /path/to/chaoxing-seat-reserve && python sign_seat.py -u config.json

# 续约到闭馆：签到后 1 小时执行，一次跑完后续所有时段（工作日 09:00 / 周末 10:00）
0 9 * * 1-5  cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json
0 10 * * 0,6 cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json

# 兜底检查：每天 12:00，上午未续满则补续，已续满自动跳过
0 12 * * *  cd /path/to/chaoxing-seat-reserve && python renew_seat.py -u config.json

# 退座：每天 22:00 闭馆后
0 22 * * * cd /path/to/chaoxing-seat-reserve && python cancel_seat.py -u config.json
```

工作日完整流程：

```text
00:00  抢座第一段（08:00-12:00）
08:00  签到（仅一次）
09:00  续约到闭馆（12-16、16-20、20-22，一次跑完）
12:00  兜底检查（已续满则跳过）
22:00  退座
```

Windows 用「任务计划程序」按同样时间点触发，程序填 `chaoxing.bat` 并加参数（「起始于」可留空，脚本会自动切到自身所在目录）：

```text
00:00            → chaoxing.bat first
08:00（工作日）/ 09:00（周末） → chaoxing.bat sign
09:00（工作日）/ 10:00（周末）、12:00 → chaoxing.bat renew
22:00            → chaoxing.bat cancel
```

`chaoxing.bat` 的行为：优先使用项目 `.venv\Scripts\python.exe`（不存在则回退系统 python），所有输出写入 `run_log.txt`；不带参数运行时显示交互菜单，输入 1-4 分别执行抢座/签到/续约/退座。

## 配置字段全表

顶层两个对象：`reserve`（必填，账号与座位配置数组）和 `bark`（选填，推送配置）。

### reserve[]（数组，至少一项）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `username` | string | 必填 | — | 学习通账号 |
| `password` | string | 必填 | — | 学习通密码 |
| `time` | array[string] | 必填 | — | `["开始","结束"]`，如 `["08:00","22:00"]`；`renew_seat.py` 把 `time[1]` 当闭馆时间 |
| `roomid` | string | 必填 | — | 图书馆 id（西安体院 `"14176"`） |
| `seatid` | array[string] | 必填 | — | 座位号列表，0 补全至 3 位（如 `["027"]`）；也兼容单个字符串 |
| `daysofweek` | array[string] | 选填 | `[]` | 预约的星期（英文名，如 `"Monday"`）；留空则每天预约 |
| `fidEnc` | string | 选填 | `"e17c5f34de515200"` | 查询当前预约列表的接口参数 |

### bark（选填）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `server` | string | 选填 | `"https://api.day.app"` | Bark 服务器地址 |
| `key` | string | 选填 | `""` | 你的 Bark 设备 key；不填则所有推送跳过 |

推送行为：所有通知的分组固定为 `超星座位`，标题随场景变化（抢座成功/失败、签到成功/失败/跳过、续约成功/失败/跳过/部分失败、退座成功/失败/跳过）。

## 常见问题

- **签到失败 / 错过签到窗口怎么办**：签到只在预约开始前后 20 分钟内有效（`sign_seat.py`、`utils/reserve.py` 注释）。错过窗口脚本无法补救，且可能积累违约记录（违约规则由平台侧决定）。
- **续约失败**：先确认第一段已经签到——续约需要访问带 `reserveId` 的签到后页面拿到加密参数，未签到会失败（`utils/reserve.py` 续约逻辑；`renew_seat.py` 失败时默认提示「可能未签到或风控」）。另外当前预约距闭馆不足 2 小时时也无法续约（平台最少 2 小时，`renew_seat.py` 会打印「剩余不足2小时，无法续约」并跳过）。
- **提示「当前没有进行中的预约」**：说明没有可操作的有效预约（时段已结束 / 当天无配置），属于正常跳过，不是错误（`renew_seat.py`、`cancel_seat.py` 的日志）。
- **预约 / 退座失败，怎么看原因**：日志会打印平台接口返回的错误消息（脚本的 `last_error` 取自接口返回的 `msg`）。常见自查项：账号密码是否正确、`roomid` / `seatid` 是否匹配、当天是否已有预约、`daysofweek` 是否包含今天。
- **提示请求过频 / 登录风控**：脚本已通过 `cookies.json` 持久化登录态来减少重复登录；若仍触发频率限制，可调大 `main.py` 里的 `SLEEPTIME`（每次尝试间隔，默认 1 秒），或等待一段时间再试（风控解除时间由平台侧决定）。
- **违约 / 次数受限类提示**：这类提示来自平台接口返回的消息，由平台侧规则决定（如未签到违约记录累计），脚本无法绕过，只能等待平台侧重置或更换账号。

## 致谢与许可证

本项目基于 [ChaoXingLibrarySeatReservation](https://gitee.com/lcz2000/ChaoXingLibrarySeatReservation)（Gitee）二次修改，按 **GNU General Public License v2.0（GPL v2）** 开源，完整许可证文本见仓库 `LICENSE` 文件。
