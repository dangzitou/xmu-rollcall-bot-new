# XMU Rollcall Bot 中文说明

一个用于登录厦门大学 TronClass、监控签到并在检测到新签到时发送提醒的命令行工具。

> **免责声明**
>
> 本项目仅用于学习、研究与个人自动化便利。使用者需自行遵守学校规定、课程要求、平台条款及适用法律。项目作者与维护者不对账号风险、数据问题、平台限制或其他使用后果负责。

---

## 功能概览

- 使用 `xmulogin` 登录厦门大学统一认证
- 持续轮询签到（默认 1 秒检查一次）
- 自动处理：
  - 数字签到（直接获取数字码并提交）
  - 雷达签到（位置求解）
- 支持多账号本地管理
- 支持缓存会话 Cookie 与刷新登录状态
- 支持按账号配置“发现新签到后发送提醒”
- 提醒发送通过独立 Hermes helper 完成，避免把聊天平台投递逻辑塞进主监控流程

---

## 安装

### 仓库根目录方式

```bash
git clone https://github.com/dangzitou/xmu-rollcall-bot.git
cd xmu-rollcall-bot
python -m pip install -e ./xmu-rollcall-cli
```

验证 CLI：

```bash
xmu --help
```

如果 `xmu` 不在 PATH 中，可以直接运行：

```bash
python -m xmu_rollcall.cli --help
```

---

## 基本使用

### macOS / Linux

```bash
cd xmu-rollcall-bot
python3 -m pip install -e ./xmu-rollcall-cli

xmu config
xmu start
```

如果命令别名不可用：

```bash
python3 -m xmu_rollcall.cli config
python3 -m xmu_rollcall.cli start
```

### Windows PowerShell

```powershell
cd C:\path\to\xmu-rollcall-bot
python -m pip install -e .\xmu-rollcall-cli

xmu config
xmu start
```

别名不可用时：

```powershell
python -m xmu_rollcall.cli config
python -m xmu_rollcall.cli start
```

---

## 常用命令

```bash
xmu config   # 添加/删除账号，并配置签到安全设置或提醒投递
xmu switch   # 切换当前账号
xmu start    # 启动签到监控
xmu refresh  # 清除当前账号缓存登录信息
xmu --help   # 查看帮助
```

---

## 提醒架构说明

新签到提醒采用“监控逻辑”和“消息投递”分离的结构：

1. `xmu_rollcall.rollcall_handler` 检测到新的签到
2. `xmu_rollcall.events.notify_new_rollcall()` 负责生成提醒 payload
3. `scripts/send_rollcall_notification.py` 作为 Hermes 桥接 helper
4. Hermes `send_message_tool` 把消息发送到配置好的聊天目标

这种做法的重点是：

- 主监控流程不用直接处理 QQ / 微信等平台细节
- 提醒目标可以按部署环境配置
- 即使提醒发送失败，也不会直接把监控主循环搞崩

> 注意：这属于“监控逻辑与投递逻辑隔离”，并不是完全平台无关。当前 helper 仍然依赖本地 Hermes 环境，并包含对 `qqbot:<openid>` 的归一化处理。

---

## 如何配置提醒

### 1）在账号层面开启提醒

先执行：

```bash
xmu config
```

选择 `m` 配置提醒投递，然后建议设置为：

- notifications enabled = yes
- notify on new rollcall = yes
- target mode = `env`
- target value = `XMU_ROLLCALL_NOTIFY_TARGET`

推荐使用 `env` 模式，因为这样可以让 `config.json` 保持可迁移，不用把聊天目标直接写死进仓库外的配置里。

### 2）设置运行时投递目标

例如，QQBot 私聊提醒：

```bash
export XMU_ROLLCALL_NOTIFY_TARGET="qqbot:YOUR_QQ_OPENID"
```

### 3）在同一环境中启动监控

```bash
xmu start
```

当检测到新的签到事件时，CLI 会立即尝试发送提醒。

---

## Helper 脚本接口

提醒 helper 接收一个 JSON 字符串参数：

```bash
python scripts/send_rollcall_notification.py '{"target":"qqbot:YOUR_QQ_OPENID","message":"hello"}'
```

当前行为：

- 对于 `qqbot:<openid>`，helper 会把 openid 映射到 Hermes 的 QQBot home-channel 发送路径
- Rollcall CLI 本身不需要知道 QQ 的底层投递实现细节
- 如果 Hermes 不可用或发送失败，主监控循环仍继续运行，并在本地输出错误

---

## 部署说明

- `scripts/send_rollcall_notification.py` 默认会寻找本地 Hermes 仓库：`~/.hermes/hermes-agent`
- 如果 Hermes 不在这个位置，可通过 `XMU_ROLLCALL_HERMES_REPO` 覆盖
- 在启动监控前，需要先确保 Hermes 已正确配置目标平台
- 生产环境更推荐用环境变量传目标，而不是把 chat id / openid 直接放进配置文件

---

## 日志说明

日志通常记录这些内容：

- 启动与账号信息
- 进入监控状态
- 检测到新的签到事件
- 签到处理结果（如已签到、回答失败等）
- 异常与退出信息

需要注意：

- 程序是**每秒检查一次**是否有新签到
- 但**不会每秒都写一行日志**
- 当前日志更偏“事件驱动”，即只有启动、发现新签到、处理结果、异常等重要节点才会落日志

---

## 已知限制

- **暂不支持二维码签到自动处理**
- 工具依赖 TronClass / XMU 的上游接口行为，上游改动后可能失效
- 提醒发送依赖外部 Hermes helper 正常可用

---

## 相关目录

- 根 README：`README.md`
- 中文 README：`README.zh-CN.md`
- CLI 文档：`xmu-rollcall-cli/README.md`
- 提醒 helper：`scripts/send_rollcall_notification.py`

---

## License

MIT
