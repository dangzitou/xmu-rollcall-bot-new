#!/usr/bin/env python3
import sys, os, time, json, traceback

CLI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(CLI_ROOT, 'xmu-rollcall-cli'))

LOG_DIR = os.environ.get('XMU_ROLLCALL_LOG_DIR', os.path.join(CLI_ROOT, '.runtime'))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'xmu-rollcall-monitor.log')
RETENTION_DAYS = 7

# Log cleanup: remove lines older than RETENTION_DAYS
def _cleanup_old_logs():
    """保留最近 RETENTION_DAYS 天的日志，其余删除。"""
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) < 1024:
        return
    cutoff = time.time() - RETENTION_DAYS * 86400
    kept = []
    with open(LOG_FILE, 'r') as f:
        for line in f:
            # 尝试从行首解析时间戳 [YYYY-MM-DD HH:MM:SS]
            if len(line) > 20 and line[0] == '[' and line[1:5].isdigit():
                try:
                    ts = time.mktime(time.strptime(line[1:20], '%Y-%m-%d %H:%M:%S'))
                    if ts < cutoff:
                        continue
                except (ValueError, OSError):
                    pass
            kept.append(line)
    if len(kept) < sum(1 for _ in open(LOG_FILE)):
        with open(LOG_FILE, 'w') as f:
            f.writelines(kept)

_cleanup_old_logs()
_last_cleanup_check = time.time()

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

_log_fh = open(LOG_FILE, 'a', buffering=1)

def p(msg):
    line = msg + '\n'
    sys.stdout.write(line)
    sys.stdout.flush()
    _log_fh.write(line)

def pe(msg, exc=None):
    """Log error with optional traceback."""
    _log_fh.write(f"[ERROR] {msg}\n")
    sys.stdout.write(f"[ERROR] {msg}\n")
    if exc:
        tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        _log_fh.write(tb + '\n')
        sys.stdout.write(tb + '\n')
    sys.stdout.flush()

p("=== XMU Direct Monitor Starting ===")

# Proxy guard
from xmu_rollcall.proxy_guard import disable_system_proxies
disable_system_proxies()

# Config
from xmu_rollcall.config import load_config, get_current_account, get_cookies_path
cfg = load_config()
acc = get_current_account(cfg)
cp = get_cookies_path(acc['id'])
p(f"Account: {acc['name']} (ID: {acc['id']})")

# Login / restore session
session = None
if os.path.exists(cp):
    import requests
    from xmu_rollcall.utils import load_session, verify_session
    from xmu_rollcall.utils import retry_request
    try:
        s = requests.Session()
        if load_session(s, cp):
            profile = retry_request(lambda: verify_session(s), max_attempts=3, delay=3, label="session_restore")
            if profile:
                session = s
                p("Session restored")
    except Exception as e:
        pe("Session restore error", e)

if not session:
    try:
        from xmulogin import xmulogin as login_fn
        p("Logging in...")
        t0 = time.time()
        session = retry_request(
            lambda: login_fn(type=3, username=acc['username'], password=acc['password']),
            max_attempts=3, delay=5, label="login",
        )
        if session:
            from xmu_rollcall.utils import save_session
            save_session(session, cp)
            p(f"Login OK ({time.time()-t0:.1f}s)")
        else:
            p("Login FAILED!")
            sys.exit(1)
    except Exception as e:
        pe("Login error", e)
        sys.exit(1)

p(f"Welcome, {acc['name']}")
p("Starting monitoring...")

base_url = "https://lnt.xmu.edu.cn"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://ids.xmu.edu.cn/authserver/login",
}
rollcalls_url = f"{base_url}/api/radar/rollcalls"
temp_data = {'rollcalls': []}
query_count = 0
start_time = time.time()
last_heartbeat_at = start_time

try:
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            raise
        
        current_time = time.time()
        elapsed = int(current_time - start_time)
        
        try:
            resp = retry_request(
                lambda: session.get(rollcalls_url, headers=headers, timeout=30),
                max_attempts=3, delay=2, label="poll",
            )
            resp.raise_for_status()
            data = resp.json()
            query_count += 1
            if query_count == 1:
                p(f"First query OK: {len(data.get('rollcalls',[]))} rollcalls")
        except Exception as e:
            if query_count == 0:
                pe(f"First query failed", e)
            # Log errors sparingly (every 10 min)
            if elapsed > 0 and elapsed % 600 < 2:
                pe(f"Recent query error ({elapsed}s)", e)
            continue
        
        # Heartbeat
        hi = 300 if (time.localtime().tm_hour >= 7 and time.localtime().tm_hour < 18) else 3600
        if current_time - last_heartbeat_at >= hi:
            lt = time.strftime('%Y-%m-%d %H:%M:%S')
            rt = f"{elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s"
            p(f"[HEARTBEAT] {lt} | Running: {rt} | Queries: {query_count}")
            last_heartbeat_at = current_time

        # Periodic log cleanup (check every heartbeat cycle)
        if current_time - _last_cleanup_check >= hi:
            _cleanup_old_logs()
            _last_cleanup_check = current_time

        # Check new rollcalls
        if temp_data != data:
            temp_data = data
            if len(temp_data.get('rollcalls', [])) > 0:
                detect_time = time.time()
                detect_ts = time.strftime('%H:%M:%S', time.localtime(detect_time))
                p(f"NEW ROLLCALL DETECTED at {detect_ts} ({len(temp_data['rollcalls'])} items)")
                try:
                    from xmu_rollcall.rollcall_handler import process_rollcalls
                    temp_data = process_rollcalls(temp_data, session, acc)

                    # Send QQ notification
                    for rc in temp_data.get('rollcalls', []):
                        cname = rc.get('course_title', rc.get('course_name', '未知课程'))
                        teacher = rc.get('created_by_name', '未知教师')
                        dept = rc.get('department_name', '')
                        if rc.get('is_radar'):
                            rtype = 'Radar rollcall'
                        elif rc.get('is_number'):
                            rtype = 'Number rollcall'
                        else:
                            rtype = 'QRcode rollcall'
                        status = rc.get('status', '已处理')

                        # Fetch student_rollcalls for number_code + answer time
                        from datetime import datetime, timezone, timedelta
                        number_code = None
                        student_answered_at = None
                        try:
                            from xmu_rollcall.verify import find_number_code
                            code_url = f"https://lnt.xmu.edu.cn/api/rollcall/{rc['rollcall_id']}/student_rollcalls"
                            code_resp = session.get(code_url, timeout=10)
                            if code_resp.status_code == 200:
                                code_data = code_resp.json()
                                number_code = find_number_code(code_data)
                                # Find current student's answer time
                                for sc in code_data.get('student_rollcalls', []):
                                    if sc.get('user_no') == acc.get('username'):
                                        student_answered_at = sc.get('updated_at')
                                        break
                        except Exception:
                            pass

                        # Parse teacher rollcall time
                        rollcall_time_str = rc.get('rollcall_time', '')
                        teacher_time_display = ''
                        rollcall_dt_bj = None
                        if rollcall_time_str:
                            try:
                                dt_utc = datetime.fromisoformat(rollcall_time_str.replace('Z', '+00:00'))
                                rollcall_dt_bj = dt_utc.astimezone(timezone(timedelta(hours=8)))
                                teacher_time_display = rollcall_dt_bj.strftime('%H:%M:%S')
                            except Exception:
                                teacher_time_display = rollcall_time_str

                        # Calculate real elapsed time from student_rollcalls.updated_at
                        answer_ts = ''
                        elapsed_sec = None
                        if student_answered_at:
                            try:
                                ans_utc = datetime.fromisoformat(student_answered_at.replace('Z', '+00:00'))
                                ans_bj = ans_utc.astimezone(timezone(timedelta(hours=8)))
                                answer_ts = ans_bj.strftime('%H:%M:%S')
                                if rollcall_dt_bj:
                                    elapsed_sec = int((ans_bj - rollcall_dt_bj).total_seconds())
                            except Exception:
                                pass
                        if not answer_ts:
                            answer_ts = time.strftime('%H:%M:%S')

                        msg = f"📢 签到提醒\n课程：{cname}\n教师：{dept} {teacher}\n类型：{rtype}\n状态：{status}"
                        if number_code:
                            msg += f"\n签到码：{number_code}"
                        if teacher_time_display:
                            msg += f"\n发起时间：{teacher_time_display}"
                        msg += f"\n签上时间：{answer_ts}"
                        if elapsed_sec is not None and elapsed_sec >= 0:
                            msg += f"\n耗时：{elapsed_sec}s"

                        notify_target = os.environ.get(
                            'XMU_ROLLCALL_NOTIFY_TARGET',
                            'qqbot:31C7A9C6D26F148A5067E9A93B86EDA9'
                        )
                        import subprocess
                        sender = os.path.join(CLI_ROOT, 'scripts', 'send_rollcall_notification.py')
                        payload = json.dumps({"target": notify_target, "message": msg})
                        subprocess.run(
                            [sys.executable, sender, payload],
                            capture_output=True, text=True, timeout=30
                        )
                        p(f"QQ notification sent for {cname}")
                except Exception as e:
                    pe("process_rollcalls or notification error", e)
                    
except KeyboardInterrupt:
    p(f"Shutdown. Queries: {query_count}, Running: {int(time.time()-start_time)}s")
    sys.exit(0)
except Exception as e:
    pe("Fatal unhandled error", e)
    sys.exit(1)
