"""XMU Rollcall CLI — 自动检测并推送厦门大学校园签到通知。

Modules:
    monitor         轮询签到事件并触发回调
    rollcall_handler 处理单次签到流程（提交 / 查询）
    verify          CAS 统一身份认证与验证码处理
    config          用户配置读写
    utils           网络请求重试、Session 持久化等工具函数
    colors          ANSI 终端颜色常量与便捷着色工具
    events          签到事件数据模型
    notifications_config  通知渠道配置
"""

__version__ = "3.4.1"

from .colors import Colors, colored, strip_ansi

__all__ = [
    "__version__",
    "Colors",
    "colored",
    "strip_ansi",
]
