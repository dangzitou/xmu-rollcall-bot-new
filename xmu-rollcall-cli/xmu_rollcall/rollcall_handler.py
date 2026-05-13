import time
import random
from .config import get_rollcall_settings
from .verify import send_code, send_radar
from .events import notify_new_rollcall

WAIT_POLL_INTERVAL = 3

def _fetch_signed_count(session, rollcall_id):
    """查询当前签到已签人数。"""
    try:
        from .verify import base_url
        resp = session.get(
            f"{base_url}/api/rollcall/{rollcall_id}/student_rollcalls",
            timeout=10,
        )
        if resp.status_code == 200:
            students = resp.json().get("student_rollcalls", [])
            return sum(1 for s in students if s.get("updated_at"))
    except Exception:
        pass
    return None

def wait_for_classmates(session, rollcall_id, settings):
    """根据配置等待足够多的同学签到后再签。"""
    mode = settings.get("wait_before_answer_mode", "none")
    if mode == "none":
        return

    if mode == "fixed":
        target = settings.get("wait_before_answer_count_min", 0)
    elif mode == "random":
        lo = settings.get("wait_before_answer_count_min", 0)
        hi = settings.get("wait_before_answer_count_max", 0)
        target = random.randint(lo, hi) if hi > lo else lo
    else:
        return

    if target <= 0:
        return

    print(f"Waiting for {target} classmate(s) to answer before signing...")
    while True:
        count = _fetch_signed_count(session, rollcall_id)
        if count is not None:
            print(f"\r  Signed: {count}/{target}", end="", flush=True)
            if count >= target:
                print()
                return
        time.sleep(WAIT_POLL_INTERVAL)

def process_rollcalls(data, session, account=None):
    """处理签到数据"""
    data_empty = {'rollcalls': []}
    result = handle_rollcalls(data, session, account)
    if False in result:
        return data_empty
    else:
        return data

def extract_rollcalls(data):
    """提取签到信息"""
    rollcalls = data['rollcalls']
    result = []
    if rollcalls:
        rollcall_count = len(rollcalls)
        for rollcall in rollcalls:
            result.append({
                'course_title': rollcall['course_title'],
                'created_by_name': rollcall['created_by_name'],
                'department_name': rollcall['department_name'],
                'is_expired': rollcall['is_expired'],
                'is_number': rollcall['is_number'],
                'is_radar': rollcall['is_radar'],
                'rollcall_id': rollcall['rollcall_id'],
                'rollcall_status': rollcall['rollcall_status'],
                'scored': rollcall['scored'],
                'status': rollcall['status']
            })
    else:
        rollcall_count = 0
    return rollcall_count, result

def wait_before_number_answer(settings):
    delay_min = settings["number_delay_min"]
    delay_max = settings["number_delay_max"]
    delay = random.randint(delay_min, delay_max) if delay_max > delay_min else delay_min

    if delay <= 0:
        return

    print(f"Waiting {delay} second(s) before answering number rollcall...")
    for remaining in range(delay, 0, -1):
        print(f"\rAnswering in {remaining:>3}s. Press Ctrl+C to cancel.", end="", flush=True)
        time.sleep(1)
    print()

def wait_before_radar_answer(settings):
    delay_min = settings.get("radar_delay_min", 0)
    delay_max = settings.get("radar_delay_max", 0)
    delay = random.randint(delay_min, delay_max) if delay_max > delay_min else delay_min

    if delay <= 0:
        return

    print(f"Waiting {delay} second(s) before answering radar rollcall...")
    for remaining in range(delay, 0, -1):
        print(f"\rAnswering in {remaining:>3}s. Press Ctrl+C to cancel.", end="", flush=True)
        time.sleep(1)
    print()

def confirm_before_answer(settings):
    if not settings["manual_confirm"]:
        return True

    answer = input("Answer this rollcall now? [y/N]: ").strip().lower()
    return answer == "y"

def handle_rollcalls(data, session, account=None):
    """处理签到流程"""
    count, rollcalls = extract_rollcalls(data)
    answer_status = [False for _ in range(count)]
    settings = get_rollcall_settings(account or {})

    if count:
        print(time.strftime("%H:%M:%S", time.localtime()), f"New rollcall(s) found!\n")
        for i in range(count):
            print(f"{i+1} of {count}:")
            print(f"Course name: {rollcalls[i]['course_title']}, rollcall created by {rollcalls[i]['department_name']} {rollcalls[i]['created_by_name']}.")

            if rollcalls[i]['is_radar']:
                temp_str = "Radar rollcall"
            elif rollcalls[i]['is_number']:
                temp_str = "Number rollcall"
            else:
                temp_str = "QRcode rollcall"
            print(f"Rollcall type: {temp_str}\n")

            # Send notification
            if account:
                try:
                    notify_new_rollcall(account, rollcalls[i])
                except Exception as e:
                    print(f"Notification error: {e}")

            if (rollcalls[i]['status'] == 'absent') & (rollcalls[i]['is_number']) & (not rollcalls[i]['is_radar']):
                wait_before_number_answer(settings)
                wait_for_classmates(session, rollcalls[i]['rollcall_id'], settings)
                if send_code(session, rollcalls[i]['rollcall_id']):
                    answer_status[i] = True
                else:
                    print("Answering failed.")
            elif rollcalls[i]['status'] == 'on_call_fine':
                print("Already answered.")
                answer_status[i] = True
            elif rollcalls[i]['is_radar']:
                wait_before_radar_answer(settings)
                wait_for_classmates(session, rollcalls[i]['rollcall_id'], settings)
                if send_radar(session, rollcalls[i]['rollcall_id']):
                    answer_status[i] = True
                else:
                    print("Answering failed.")
            else:
                # QRcode rollcall - 无法自动处理，仅通知
                print("QRcode rollcall - please scan the QR code manually.")

    return answer_status

