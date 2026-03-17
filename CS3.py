import psutil
import os
import time
import chardet
import re
import threading
import winsound
import tkinter as tk
import sys  # ⭐ 必须加

GAME_NAME = "javaw.exe"

# ===== 兼容 EXE / 脚本 双环境 =====
if getattr(sys, 'frozen', False):
    # 打包成 EXE
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 直接运行 .py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 日志目录就在 EXE 或脚本同目录
LOG_DIR =  BASE_DIR

MONSTER_PATTERN = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\].*?(十万|百万|千万|亿万)年混兽\?([\u4e00-\u9fa5]{2,10})\s*身上摸到了\s*(\d+(\.\d+)?)\s*金币"
)

monster_records = []
predicted_records = []
seen_lines = set()


# ===== 时间工具 =====
def time_to_seconds(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def add_one_hour(sec):
    return sec + 3600


def is_within_5_minutes(t1, t2):
    return abs(t1 - t2) <= 300  # 5分钟


def format_time(sec):
    sec = sec % 86400
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ===== 核心：2小时窗口清理 =====
def clean_old_data(current_sec):
    global predicted_records, monster_records
    predicted_records = [
        r for r in predicted_records
        if abs(current_sec - r["预测时间"]) <= 7200
    ]
    monster_records = [
        r for r in monster_records
        if abs(current_sec - r["时间秒"]) <= 7200
    ]


# ===== 游戏检测 =====
def is_game_running():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == GAME_NAME:
            return True
    return False


# ===== 获取最新日志 =====
def get_latest_log():
    if not os.path.exists(LOG_DIR):
        print(f"日志目录不存在: {LOG_DIR}")
        return None
    log_files = [f for f in os.listdir(LOG_DIR) if f.lower().endswith((".log", ".txt"))]
    if not log_files:
        return None
    latest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(LOG_DIR, f)))
    return os.path.join(LOG_DIR, latest_log)


# ===== 编码检测 =====
def detect_encoding(file_path):
    with open(file_path, "rb") as f:
        raw = f.read(5000)
        result = chardet.detect(raw)
        return result['encoding'] or 'utf-8'


# ===== 弹窗提醒工具 =====
def alert_left_top_with_sound(title, message, duration=3):
    def run():
        # 声音循环线程
        def play_sound():
            end_time = time.time() + duration
            while time.time() < end_time:
                winsound.Beep(1000, 500)
                time.sleep(0.1)

        threading.Thread(target=play_sound, daemon=True).start()

        # Tkinter窗口
        root = tk.Tk()
        root.title(title)
        root.geometry(f"300x100+0+0")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        label = tk.Label(root, text=message, font=("微软雅黑", 12))
        label.pack(expand=True)
        root.after(duration * 1000, root.destroy)
        root.mainloop()

    threading.Thread(target=run, daemon=True).start()


# ===== 核心解析 =====
def parse_monster(line):
    if line in seen_lines:
        return
    seen_lines.add(line)

    match = MONSTER_PATTERN.search(line)
    if not match:
        return

    h, m, s = match.group(1), match.group(2), match.group(3)
    year = match.group(4)
    monster = match.group(5)
    gold = float(match.group(6))

    current_sec = time_to_seconds(h, m, s)

    clean_old_data(current_sec)

    monster_records.append({
        "时间": f"{h}:{m}:{s}",
        "时间秒": current_sec,
        "年份": year,
        "魂兽": monster,
        "金币": gold
    })

    predicted_sec = add_one_hour(current_sec)
    predicted_records.append({
        "原时间": current_sec,
        "预测时间": predicted_sec,
        "魂兽": monster,
        "已提醒": False
    })

    print("\n===== 检测到魂兽击杀 =====")
    print(f"时间: {h}:{m}:{s}, 年份: {year}, 魂兽: {monster}, 金币: {gold}")
    print(f"预测时间(+1小时): {format_time(predicted_sec)}")
    print("========================\n")


# ===== 实时监听日志 =====
def tail_log(file_path):
    encoding = detect_encoding(file_path)
    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.3)
                continue
            line = line.strip()
            print(line)
            parse_monster(line)


# ===== 提醒线程 =====
def reminder_loop():
    while True:
        now_sec = time_to_seconds(*time.strftime("%H %M %S").split())
        clean_old_data(now_sec)
        for record in predicted_records:
            # 提前 5 分钟提醒
            if not record.get("已提醒") and is_within_5_minutes(now_sec, record["预测时间"] - 300):
                record["已提醒"] = True
                alert_left_top_with_sound(
                    "魂兽预测提醒",
                    f"魂兽 {record['魂兽']} 预计在 {format_time(record['预测时间'])} 出现！",
                    duration=3
                )
        time.sleep(1)


# ===== 主程序 =====
def main():
    if not is_game_running():
        print("游戏未启动")
        return

    print("游戏已启动")

    latest_log = get_latest_log()
    if not latest_log:
        print(f"日志文件不存在，请确认目录: {LOG_DIR}")
        return

    threading.Thread(target=reminder_loop, daemon=True).start()
    print("\n===== 实时监听日志 =====")
    tail_log(latest_log)


if __name__ == "__main__":
    main()