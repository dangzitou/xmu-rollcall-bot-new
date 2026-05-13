import time
import os
import sys
import requests
import shutil
import re
from . import __version__
from .proxy_guard import disable_system_proxies

disable_system_proxies()

from xmulogin import xmulogin
from .utils import clear_screen, save_session, load_session, verify_session, supports_interactive_terminal, retry_request
from .utils import base_url, headers
from .rollcall_handler import process_rollcalls
from .config import get_cookies_path
from .colors import Colors

interval = 1

BOLD_LABEL = f"{Colors.BOLD}"
CYAN_TEXT = f"{Colors.OKCYAN}"
GREEN_TEXT = f"{Colors.OKGREEN}"
YELLOW_TEXT = f"{Colors.WARNING}"
END = Colors.ENDC
INTERACTIVE_TTY = supports_interactive_terminal()

def get_terminal_width():
    """获取终端宽度"""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text):
    """移除ANSI颜色代码以计算实际文本长度"""
    return _ANSI_ESCAPE.sub('', text)

def center_text(text, width=None):
    """居中文本"""
    if width is None:
        width = get_terminal_width()
    text_len = len(strip_ansi(text))
    if text_len >= width:
        return text
    left_padding = (width - text_len) // 2
    return ' ' * left_padding + text

def print_banner():
    """打印美化的横幅"""
    width = get_terminal_width()
    line = '=' * width

    title1 = "XMU Rollcall Bot CLI"
    title2 = f"Version {__version__}"

    if INTERACTIVE_TTY:
        print(f"{Colors.OKCYAN}{line}{Colors.ENDC}")
        print(center_text(f"{Colors.BOLD}{title1}{Colors.ENDC}"))
        print(center_text(f"{Colors.GRAY}{title2}{Colors.ENDC}"))
        print(f"{Colors.OKCYAN}{line}{Colors.ENDC}")
    else:
        print(line)
        print(center_text(title1))
        print(center_text(title2))
        print(line)

def print_separator(char="-"):
    """打印分隔线"""
    width = get_terminal_width()
    line = char * width
    if INTERACTIVE_TTY:
        print(f"{Colors.GRAY}{line}{Colors.ENDC}")
    else:
        print(line)

def format_time(seconds):
    """格式化时间显示"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

_COLOR_PALETTE = (
    Colors.FAIL,
    Colors.WARNING,
    Colors.OKGREEN,
    Colors.OKCYAN,
    Colors.OKBLUE,
    Colors.HEADER
)
_COLOR_COUNT = len(_COLOR_PALETTE)

def get_colorful_text(text, color_offset=0):
    """为文本的每个字符应用不同的颜色"""
    return ''.join(
        _COLOR_PALETTE[(i + color_offset) % _COLOR_COUNT] + char
        for i, char in enumerate(text)
    ) + Colors.ENDC

def print_footer_text(color_offset=0):
    """打印底部彩色文字"""
    text = "XMU-Rollcall-Bot @ KrsMt"
    colored = get_colorful_text(text, color_offset)
    print(center_text(colored))

def print_dashboard(name, start_time, query_count, banner_frame=0, show_banner=True):
    """打印主仪表板"""
    clear_screen()
    print_banner()

    local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

    if time.localtime().tm_hour < 12 and time.localtime().tm_hour >= 5:
        greeting = "Good morning"
    elif time.localtime().tm_hour < 18 and time.localtime().tm_hour >= 12:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    now = time.time()
    running_time = int(now - start_time)

    print(f"\n{Colors.OKGREEN}{Colors.BOLD}{greeting}, {name}!{Colors.ENDC}\n")

    print(f"{Colors.BOLD}SYSTEM STATUS{Colors.ENDC}")
    print_separator()
    print(f"{Colors.BOLD}Current Time:{Colors.ENDC}    {Colors.OKCYAN}{local_time}{Colors.ENDC}")
    print(f"{Colors.BOLD}Running Time:{Colors.ENDC}    {Colors.OKGREEN}{format_time(running_time)}{Colors.ENDC}")
    print(f"{Colors.BOLD}Query Count:{Colors.ENDC}     {Colors.WARNING}{query_count}{Colors.ENDC}")

    print(f"\n{Colors.BOLD}ROLLCALL MONITOR{Colors.ENDC}")
    print_separator()
    print(f"{Colors.OKGREEN}Status:{Colors.ENDC} Active - Monitoring for new rollcalls...")
    print(f"{Colors.GRAY}Checking every {interval} second(s){Colors.ENDC}")
    print(f"{Colors.GRAY}Press Ctrl+C to exit{Colors.ENDC}\n")
    print_separator()

    if show_banner:
        print()
        print_footer_text(banner_frame)

def print_login_status(message, is_success=True):
    """打印登录状态"""
    if is_success:
        print(f"{Colors.OKGREEN}[SUCCESS]{Colors.ENDC} {message}")
    else:
        print(f"{Colors.FAIL}[FAILED]{Colors.ENDC} {message}")

TIME_LINE = 10
RUNTIME_LINE = 11
QUERY_LINE = 12
FOOTER_LINE = 20
DAYTIME_HEARTBEAT_INTERVAL = 300
NIGHTTIME_HEARTBEAT_INTERVAL = 3600


def get_heartbeat_interval_for_hour_minute(hour, minute):
    """根据时段返回心跳间隔（秒）。白天 07:00-18:29 为 5 分钟，其余为 1 小时。"""
    if (hour > 7 or (hour == 7 and minute >= 0)) and (hour < 18 or (hour == 18 and minute < 30)):
        return DAYTIME_HEARTBEAT_INTERVAL
    return NIGHTTIME_HEARTBEAT_INTERVAL


def log_heartbeat(local_time, running_time, query_count):
    """在非交互模式下输出周期性心跳日志。"""
    if INTERACTIVE_TTY:
        return
    print(
        f"[HEARTBEAT] Current Time: {local_time} | "
        f"Running Time: {running_time} | Query Count: {query_count}",
        flush=True,
    )

def update_status_line(line_num, label, value, color):
    """更新指定行的状态信息，不清屏"""
    if not INTERACTIVE_TTY:
        return
    sys.stdout.write("\033[?25l")
    sys.stdout.write("\033[s")
    sys.stdout.write(f"\033[{line_num};0H")
    sys.stdout.write("\033[2K")
    sys.stdout.write(f"{Colors.BOLD}{label}{Colors.ENDC}    {color}{value}{Colors.ENDC}")
    sys.stdout.write("\033[u")
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def update_footer_text():
    """更新底部彩色文字，不清屏"""
    if not INTERACTIVE_TTY:
        return
    text = "XMU-Rollcall-Bot @ KrsMt"
    colored = get_colorful_text(text, 0)
    width = get_terminal_width()

    sys.stdout.write("\033[?25l")
    sys.stdout.write("\033[s")
    sys.stdout.write(f"\033[{FOOTER_LINE};0H")
    sys.stdout.write("\033[2K")

    text_len = len(text)
    left_padding = (width - text_len) // 2
    sys.stdout.write(' ' * left_padding + colored)

    sys.stdout.write("\033[u")
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def start_monitor(account):
    """启动监控程序"""
    USERNAME = account['username']
    PASSWORD = account['password']
    ACCOUNT_ID = account.get('id', 1)
    ACCOUNT_NAME = account.get('name', '')
    # LATITUDE = account.get('latitude', 0)
    # LONGITUDE = account.get('longitude', 0)

    # 设置全局位置信息
    # set_location(LATITUDE, LONGITUDE)

    cookies_path = get_cookies_path(ACCOUNT_ID)
    rollcalls_url = f"{base_url}/api/radar/rollcalls"
    session = None

    # 初始化
    clear_screen()
    print_banner()
    print(f"\n{Colors.BOLD}Initializing XMU Rollcall Bot...{Colors.ENDC}\n")
    print_separator()

    print(f"\n{Colors.OKCYAN}[Step 1/3]{Colors.ENDC} Checking credentials...")

    if os.path.exists(cookies_path):
        print(f"{Colors.OKCYAN}[Step 2/3]{Colors.ENDC} Found cached session, attempting to restore...")
        session_candidate = requests.Session()
        if load_session(session_candidate, cookies_path):
            profile = verify_session(session_candidate)
            if profile:
                session = session_candidate
                print_login_status("Session restored successfully", True)
            else:
                print_login_status("Session expired, will re-login", False)
        else:
            print_login_status("Failed to load session", False)

    if not session:
        print(f"{Colors.OKCYAN}[Step 2/3]{Colors.ENDC} Logging in with credentials...")
        time.sleep(2)
        session = xmulogin(type=3, username=USERNAME, password=PASSWORD)
        if session:
            save_session(session, cookies_path)
            print_login_status("Login successful", True)
        else:
            print_login_status("Login failed. Please check your credentials", False)
            time.sleep(5)
            sys.exit(1)

    print(f"{Colors.OKCYAN}[Step 3/3]{Colors.ENDC} Fetching user profile...")
    # profile = session.get(f"{base_url}/api/profile", headers=headers).json()
    # name = profile["name"]
    print_login_status(f"Welcome, {ACCOUNT_NAME}", True)

    print(f"\n{Colors.OKGREEN}{Colors.BOLD}Initialization complete{Colors.ENDC}")
    print(f"\n{Colors.GRAY}Starting monitor in 3 seconds...{Colors.ENDC}")
    time.sleep(3)

    # 主循环
    temp_data = {'rollcalls': []}
    query_count = 0
    start_time = time.time()

    print_dashboard(ACCOUNT_NAME, start_time, query_count, 0, show_banner=False)

    footer_initialized = False
    _last_query_time = 0
    last_heartbeat_at = start_time

    try:
        while True:
            try:
                time.sleep(0.1)
            except KeyboardInterrupt:
                raise

            try:
                current_time = time.time()

                if not footer_initialized:
                    footer_initialized = True
                    update_footer_text()

                elapsed = int(current_time - start_time)
                if elapsed > _last_query_time:
                    _last_query_time = elapsed
                    data = retry_request(
                        lambda: session.get(rollcalls_url, headers=headers, timeout=30),
                        max_attempts=3, delay=2, label="poll",
                    ).json()
                    query_count += 1

                    local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                    running_time = format_time(elapsed)

                    update_status_line(TIME_LINE, "Current Time:", local_time, Colors.OKCYAN)
                    update_status_line(RUNTIME_LINE, "Running Time:", running_time, Colors.OKGREEN)
                    update_status_line(QUERY_LINE, "Query Count: ", str(query_count), Colors.WARNING)

                    heartbeat_interval = get_heartbeat_interval_for_hour_minute(
                        time.localtime(current_time).tm_hour,
                        time.localtime(current_time).tm_min,
                    )
                    if current_time - last_heartbeat_at >= heartbeat_interval:
                        log_heartbeat(local_time, running_time, query_count)
                        last_heartbeat_at = current_time

                    if temp_data != data:
                        temp_data = data
                        if len(temp_data['rollcalls']) > 0:
                            clear_screen()
                            width = get_terminal_width()
                            print(f"\n{Colors.WARNING}{Colors.BOLD}{'!' * width}{Colors.ENDC}")
                            print(center_text(f"{Colors.WARNING}{Colors.BOLD}NEW ROLLCALL DETECTED{Colors.ENDC}"))
                            print(f"{Colors.WARNING}{Colors.BOLD}{'!' * width}{Colors.ENDC}\n")
                            temp_data = process_rollcalls(temp_data, session, account)
                            print_separator("=")
                            print(f"\n{center_text(f'{Colors.GRAY}Press Ctrl+C to exit, continuing monitor...{Colors.ENDC}')}\n")
                            try:
                                time.sleep(3)
                            except KeyboardInterrupt:
                                raise
                            print_dashboard(ACCOUNT_NAME, start_time, query_count, 0)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                clear_screen()
                print(f"\n{center_text(f'{Colors.FAIL}{Colors.BOLD}Error occurred:{Colors.ENDC} {str(e)}')}")
                print(f"{center_text(f'{Colors.GRAY}Exiting...{Colors.ENDC}')}\n")
                sys.exit(1)
    except KeyboardInterrupt:
        clear_screen()
        print(f"\n{center_text(f'{Colors.WARNING}Shutting down gracefully...{Colors.ENDC}')}")
        print(f"{center_text(f'{Colors.GRAY}Total queries performed: {query_count}{Colors.ENDC}')}")
        print(f"{center_text(f'{Colors.GRAY}Total running time: {format_time(int(time.time() - start_time))}{Colors.ENDC}')}")
        print(f"\n{center_text(f'{Colors.OKGREEN}Goodbye{Colors.ENDC}')}\n")
        sys.exit(0)
