#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛博保姆 · 本地定时提醒
--------------------------------
零依赖：只用 Python 标准库（tkinter / winsound / subprocess）。
Windows 下双击运行，或 `python nanny_reminder.py`。

功能
  1. 按 SCHEDULE 定点弹窗提醒（置顶、AUTO_CLOSE_SEC 秒后自动消失）
  2. 久坐循环提醒（每 SIT_EVERY_MIN 分钟）
  3. 可选语音播报（Windows SAPI，中文音色取决于系统已装语音包）
  4. 提醒记录写入同目录 nanny_log.txt

改配置直接改「配置区」，不用动逻辑。停止：Ctrl+C 或关闭控制台。
"""

import os
import sys
import time
import datetime
import subprocess
import threading

# ============ 配置区 ============
SCHEDULE = [
    ("07:00", "起床。别按掉了继续睡。"),
    ("07:30", "喝水，然后开始今天的第一件事。"),
    ("09:00", "专注 45 分钟，手机翻过去。"),
    ("10:30", "起来走两分钟，别装死。"),
    ("12:00", "吃饭。边吃边刷手机不算休息。"),
    ("14:00", "下午最困，先喝水再开工。"),
    ("16:00", "检查任务列表，还有几项没动？"),
    ("18:30", "运动 20 分钟，别找借口。"),
    ("21:00", "收尾今天的活，别再开新的。"),
    ("22:30", "洗漱，准备关机。"),
    ("23:20", "该睡了。明天还要打仗。"),
]

SIT_EVERY_MIN = 50      # 久坐提醒间隔（分钟），0 = 关闭
VOICE = True            # 是否语音播报
VOICE_RATE = 1          # -10 ~ 10
AUTO_CLOSE_SEC = 30     # 弹窗自动关闭秒数
TICK_MS = 1000          # 内部轮询间隔

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nanny_log.txt")
# ================================


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def beep() -> None:
    """非阻塞提示音。非 Windows 静默跳过。"""
    if sys.platform != "win32":
        return

    def _run():
        try:
            import winsound
            for freq in (740, 980, 1180):
                winsound.Beep(freq, 130)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def speak(text: str) -> None:
    """调 Windows SAPI 朗读。失败静默降级。"""
    if not VOICE or sys.platform != "win32":
        return
    safe = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.Rate = {VOICE_RATE};"
        f"$s.Speak('{safe}')"
    )

    def _run():
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                timeout=25,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


class Nanny:
    def __init__(self):
        self.fired = set()
        self.day = datetime.date.today()
        self.last_sit = time.time()
        self.count = 0
        self.root = None

    # ---------- 弹窗 ----------
    def popup(self, message: str):
        import tkinter as tk

        win = tk.Toplevel(self.root)
        win.title("赛博保姆")
        win.attributes("-topmost", True)
        win.configure(bg="#ffffff")
        win.resizable(False, False)

        w, h = 440, 208
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        off = self.count * 24
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3 + off}")
        self.count = (self.count + 1) % 5

        tk.Frame(win, bg="#5546ff", height=4).pack(fill="x")
        tk.Label(win, text="赛博保姆", font=("Microsoft YaHei", 15, "bold"),
                 fg="#12141c", bg="#ffffff").pack(anchor="w", padx=22, pady=(16, 4))
        tk.Label(win, text=message, font=("Microsoft YaHei", 13),
                 fg="#4a4f60", bg="#ffffff", wraplength=w - 44,
                 justify="left").pack(anchor="w", padx=22)
        tk.Button(win, text="我知道了", font=("Microsoft YaHei", 11, "bold"),
                  bg="#5546ff", fg="#ffffff", activebackground="#4636f2",
                  activeforeground="#ffffff", relief="flat", bd=0,
                  padx=20, pady=7, cursor="hand2",
                  command=win.destroy).pack(pady=(14, 0))

        win.after(AUTO_CLOSE_SEC * 1000, win.destroy)

    # ---------- 触发 ----------
    def fire(self, message: str, tag: str):
        log(f"{tag} | {message}")
        beep()
        speak(message)
        try:
            self.popup(message)
        except Exception:
            pass  # 无 GUI 环境只留日志

    # ---------- 主循环 ----------
    def tick(self):
        try:
            now = datetime.datetime.now()
            if now.date() != self.day:      # 跨天重置
                self.day = now.date()
                self.fired.clear()
                log("新的一天，提醒计划已重置。")

            hm = now.strftime("%H:%M")
            for t, msg in SCHEDULE:
                if t == hm and hm not in self.fired:
                    self.fired.add(hm)
                    self.fire(msg, "定点")

            if SIT_EVERY_MIN > 0 and time.time() - self.last_sit >= SIT_EVERY_MIN * 60:
                self.last_sit = time.time()
                self.fire(f"你已经坐了 {SIT_EVERY_MIN} 分钟。起来动两分钟，别死扛。", "久坐")
        except Exception as exc:
            log(f"异常：{exc!r}")
        self.root.after(TICK_MS, self.tick)

    def run(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        log("赛博保姆已上线。关掉控制台或 Ctrl+C 停止。")
        self.root.after(500, self.tick)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            log("保姆下线。")


if __name__ == "__main__":
    Nanny().run()
