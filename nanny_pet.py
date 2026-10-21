# -*- coding: utf-8 -*-
"""
诺诺 · 赛博管家（桌宠版）

一只常驻桌面的小人：无边框、悬浮、可拖动，会说话、会催你、能计时。
面板仍然是 index.html（双击小人打开），桌宠负责“在场感”。

运行：
    python nanny_pet.py
依赖：
    Python 3.9+（需带 tkinter）、Pillow
"""

import ctypes
import json
import os
import random
import sys
import time
import webbrowser

import tkinter as tk
from tkinter import font as tkfont, messagebox

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    Image = None

try:
    import winsound
except ImportError:
    winsound = None

APP_NAME = "诺诺"
APP_SUB = "赛博管家"
APP_VER = "3.2"
PANEL_URL = "https://minj65446-ops.github.io/cyber-nanny/"

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(ROOT_DIR, "assets", "pet")
CONF_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "cyber-nanny")
CONF_FILE = os.path.join(CONF_DIR, "pet.json")
LOCK_FILE = os.path.join(CONF_DIR, "pet.lock")
SIGNAL_FILE = os.path.join(CONF_DIR, "pet.signal")

KEY = "#ff00ff"          # 透明色键，选洋红是因为立绘里没有这个颜色

# ---------------------------------------------------------------- 台词

LINES = {
    "savage": {
        "greet": ["我在。别指望我今天嘴下留情。", "回来了？任务列表还等着你。", "别看我，看你的待办。"],
        "idle":  ["手在动，进度条没动。", "你确定现在这件事最重要？", "别发呆，要么干，要么去歇。", "我就静静看着你磨蹭。"],
        "praise": ["行吧，这次算你干了点正事。", "勉强及格，继续。", "别飘，还有一堆没做。"],
        "nag":   ["该动了。别假装没看见。", "坐到天荒地老也算努力？", "你现在做的，是今天最重要的事吗？"],
        "water": ["喝水。现在。", "水杯是摆设吗？"],
        "sleep": ["该睡了。手机放下。", "熬夜换来的效率都是假的。"],
        "wake":  ["起床了。别再躺五分钟。", "早上的时间最值钱。"],
    },
    "gentle": {
        "greet": ["今天也一起慢慢来吧。", "我在旁边，别急。", "先照顾自己，再谈效率。"],
        "idle":  ["要不要先做最小的一步？", "累的话就休息两分钟，我等 你。", "喝口水，再继续。"],
        "praise": ["做得很好，我记下了。", "看，你可以的。", "辛苦啦，给自己一点奖励。"],
        "nag":   ["现在开始也完全来得及。", "拆成两半，我陪你做。"],
        "water": ["喝点水吧，就一口。", "水杯该续上了。"],
        "sleep": ["该休息了，明天才有精神。", "身体比进度重要。"],
        "wake":  ["早上好，慢慢清醒。", "新的一天，先深呼吸三次。"],
    },
    "robot": {
        "greet": ["系统就绪。开始采集行为数据。", "检测到宿主在线。合规率待评估。"],
        "idle":  ["单位时间产出低于阈值。", "等待指令。或由我分配。"],
        "praise": ["行为记录已归档。评分上调。", "执行符合预期。"],
        "nag":   ["检测到任务队列堆积。建议立即处理。", "注意力漂移。已记录。"],
        "water": ["补水指令：执行。", "体液赤字，请摄入液体。"],
        "sleep": ["进入睡眠窗口。请关闭终端。", "褪黑素分泌窗口开启。"],
        "wake":  ["唤醒程序完成。请启动日间循环。"],
    },
    "drill": {
        "greet": ["站直！今天的时间归我管。", "磨磨蹭蹭，我看着就来气。"],
        "idle":  ["愣着干什么，动起来！", "坐着能想出个屁来！"],
        "praise": ["这才像个人样！", "合格！别指望我夸第二次。"],
        "nag":   ["少废话，多干活！", "你的对手已经在跑了。"],
        "water": ["喝水！身体是革命的本钱！"],
        "sleep": ["熄灯！明天还有仗要打！"],
        "wake":  ["起床！太阳都看不下去了！"],
    },
}
PERSONA_NAME = {"savage": "毒舌总管", "gentle": "温柔姐姐", "robot": "冷面机械", "drill": "军训教官"}

SCHEDULE = [
    ("07:00", "wake"),
    ("10:00", "water"),
    ("12:30", "water"),
    ("14:30", "nag"),
    ("16:30", "water"),
    ("19:00", "nag"),
    ("22:30", "sleep"),
]

EXPR_OF = {
    "greet": "normal", "idle": "normal", "praise": "happy",
    "nag": "angry", "water": "happy", "sleep": "sleepy", "wake": "happy",
}
IMAGES = {
    "normal": "nono-normal.png",
    "happy": "nono-happy.png",
    "angry": "nono-angry.png",
    "sleepy": "nono-sleepy.png",
}

DEFAULT_CFG = {
    "x": None, "y": None, "scale": 0.9, "topmost": True,
    "persona": "savage", "quiet": False, "pomos": 0, "pomo_date": "",
    "daily": {},          # 桌宠自己的轻量打卡，跨天自动重置
}

CHECKS = [("wake", "起床"), ("exercise", "运动 20 分钟"), ("read", "阅读 / 学习"), ("sleep", "按时睡觉")]


# ---------------------------------------------------------------- 工具

def dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def single_instance():
    """同一时间只允许一只桌宠。"""
    os.makedirs(CONF_DIR, exist_ok=True)
    try:
        import msvcrt
        f = open(LOCK_FILE, "a+")   # 首次运行时文件还不存在，必须用 a+
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        return f
    except Exception:
        return None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "CyberNannyPet"


def startup_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except Exception:
        return False


def set_startup(on):
    """返回 None 表示成功，否则返回错误文本。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                exe = sys.executable
                pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
                if os.path.exists(pw):
                    exe = pw                      # 用 pythonw 才不会弹黑框
                cmd = f'"{exe}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        return None
    except Exception as e:
        return str(e)


def work_area():
    """任务栏之外的可用区域，避免小人一半藏在任务栏后面。"""
    try:
        import ctypes.wintypes as wt
        r = wt.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        if r.right > r.left and r.bottom > r.top:
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, None, None


def log(msg):
    """桌宠崩了也要留下痕迹，不然用户只会看到它“自己消失了”。"""
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(os.path.join(CONF_DIR, "pet.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg).rstrip() + "\n")
    except Exception:
        pass


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CONF_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f) or {})
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(CONF_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def beep(kind="soft"):
    if not winsound:
        return
    try:
        if kind == "alert":
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


# ---------------------------------------------------------------- 桌宠

class DeskPet:
    def __init__(self):
        self.cfg = load_cfg()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} · {APP_SUB}")
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        try:
            self.root.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        self.root.attributes("-topmost", bool(self.cfg.get("topmost", True)))

        self.scale = float(self.cfg.get("scale") or 0.9)
        self.persona = self.cfg.get("persona") or "savage"
        self.quiet = bool(self.cfg.get("quiet"))
        self.expr = "normal"
        self.photos = {}
        self.line = ""
        self.hold_until = 0
        self.drag_off = (0, 0)
        self.drag_moved = False
        self.pomo_end = 0
        self.pomo_len = 0
        self.last_schedule = ""
        self.next_idle = time.time() + random.randint(240, 600)
        self.blink_at = time.time() + random.randint(8, 20)

        self._build()
        w, _, _, _, _, h = self._metrics()
        self.root.geometry(f"{w}x{h}+0+0")
        self._place_start()
        self._load_images()
        self.say("greet")

        self.root.after(600, self._raise_top)
        self.root.after(200, self._tick)
        self.root.after(500, self._blink_loop)

    # ---------------------------------------------------------- 构建

    def _metrics(self):
        s = self.scale
        w = int(232 * s)
        pet_w = int(w * 0.90)
        pet_h = int(pet_w * 441 / 348)
        bubble_h = int(42 * s)          # 固定两行高度，换行时人物不跳
        gap = int(4 * s)
        bottom = int(7 * s)             # 底部留一点透明，渐隐后不像被切掉
        h = bubble_h + gap + pet_h + bottom
        return w, pet_w, pet_h, bubble_h, gap, h

    def _build(self):
        w, pet_w, pet_h, bh, gap, h = self._metrics()
        self.canvas = tk.Canvas(self.root, width=w, height=h, bg=KEY,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()

        fsize = max(9, int(12 * self.scale))
        self.f_bubble = tkfont.Font(family="Microsoft YaHei", size=-fsize)
        self.f_tip = tkfont.Font(family="Microsoft YaHei", size=-max(8, int(10 * self.scale)))

        self.cv_bubble = round_rect(self.canvas, 2, 2, w - 2, bh, int(12 * self.scale),
                                    fill="#ffffff", outline="#e2e4ef", width=1)
        self.cv_text = self.canvas.create_text(
            w / 2, bh / 2, text="", width=w - int(20 * self.scale),
            font=self.f_bubble, fill="#12141c", justify="center")
        self.cv_img = self.canvas.create_image(w / 2, bh + gap + pet_h / 2, image=None)

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", self._dbl)
        self.canvas.bind("<Button-3>", self._menu)
        self.canvas.bind("<MouseWheel>", self._wheel)

    def _place_start(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        wx1, wy1, wx2, wy2 = work_area()
        wx2 = wx2 or sw
        wy2 = wy2 or sh
        w, _, _, _, _, h = self._metrics()
        x = self.cfg.get("x")
        y = self.cfg.get("y")
        if x is None or y is None:
            x = wx2 - w - int(40 * self.scale)
            y = wy2 - h - int(16 * self.scale)
        # 屏幕变化后兜底，别把小人留在屏幕外
        x = max(-w // 2, min(int(x), sw - w // 2))
        y = max(0, min(int(y), sh - h // 2))
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _load_images(self):
        _, pet_w, _, _, _, _ = self._metrics()
        if Image is None:
            self.canvas.create_text(20, 20, text="缺少 Pillow\npip install pillow",
                                    fill="#e5484d", font=self.f_bubble)
            return
        for key, fn in IMAGES.items():
            path = os.path.join(ASSET_DIR, fn)
            try:
                im = Image.open(path).convert("RGBA")
            except Exception:
                continue
            k = pet_w / im.width
            im = im.resize((pet_w, max(1, int(im.height * k))), Image.LANCZOS)
            # 关键：先把 alpha 二值化，再贴到色键上。
            # 否则缩放产生的半透明边缘会和洋红混合，人物周围会出现一圈粉边。
            alpha = im.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
            im.putalpha(alpha)
            bg = Image.new("RGB", im.size, KEY)
            bg.paste(im, (0, 0), im)          # mask 已二值化，不会混色
            self.photos[key] = ImageTk.PhotoImage(bg)
        if not self.photos:
            self.canvas.create_text(20, 20, text="缺图：assets/pet/", fill="#e5484d", font=self.f_bubble)
        else:
            self._set_expr("normal", redraw=False)

    # ---------------------------------------------------------- 绘制

    def _set_expr(self, name, redraw=True):
        if name not in self.photos:
            return
        self.expr = name
        self.canvas.itemconfigure(self.cv_img, image=self.photos[name])
        if redraw:
            self.canvas.tag_raise(self.cv_text)

    def say(self, cat="idle", text=None, hold=7.0, expr=None, silent=False):
        pool = LINES.get(self.persona, LINES["savage"])
        if text is None:
            text = random.choice(pool.get(cat) or pool["idle"])
        self.line = text
        self.hold_until = time.time() + hold
        w, _, _, bh, _, _ = self._metrics()
        self._wrap(text, w - int(26 * self.scale))
        self.canvas.itemconfigure(self.cv_text, text=self.wrapped)
        self._set_expr(expr or EXPR_OF.get(cat, "normal"))
        if not silent:
            beep("soft")

    def _wrap(self, text, maxw):
        """按像素宽度手动折行，最多 3 行；带简单避头点，标点不单独起行。"""
        no_start = "。，、；：？！）】》”’…%"
        lines, cur = [], ""
        for ch in text:
            if cur and self.f_bubble.measure(cur + ch) > maxw:
                if ch in no_start:      # 标点跟着上一行，宁可略微超宽
                    cur += ch
                    continue
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        if len(lines) > 3:
            lines = lines[:3]
            lines[-1] = lines[-1][:-1] + "…"
        self.wrapped = "\n".join(lines)

    # ---------------------------------------------------------- 交互

    def _press(self, e):
        self._raise_top()
        if getattr(self, "_click_job", None):
            try: self.root.after_cancel(self._click_job)
            except Exception: pass
            self._click_job = None
        self.drag_off = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())
        self.drag_moved = False

    def _drag(self, e):
        w, _, _, _, _, h = self._metrics()
        x = e.x_root - self.drag_off[0]
        y = e.y_root - self.drag_off[1]
        if abs(x - self.root.winfo_x()) > 3 or abs(y - self.root.winfo_y()) > 3:
            self.drag_moved = True
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = max(-w // 3, min(x, sw - w * 2 // 3))
        y = max(0, min(y, sh - h // 3))
        self.root.geometry(f"+{x}+{y}")

    def _release(self, e):
        if self.drag_moved:
            self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
            save_cfg(self.cfg)
        else:
            # 延迟一点再说话：双击打开面板时就不该先冒一句台词
            self._click_job = self.root.after(230, lambda: self.say("idle"))

    def _wheel(self, e):
        step = 0.1 if e.delta > 0 else -0.1
        self.set_scale(round(self.scale + step, 2))

    def _raise_top(self):
        """Windows 上多个置顶窗口会互相抢层级，交互时把自己提回最上面。"""
        if not self.cfg.get("topmost", True):
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            ctypes.windll.user32.SetWindowPos(
                hwnd, -1, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0010)   # HWND_TOPMOST / NOSIZE / NOMOVE / NOACTIVATE
        except Exception:
            pass

    def set_scale(self, s):
        s = max(0.65, min(1.5, s))
        if abs(s - self.scale) < 0.01:
            return
        self.scale = s
        self.cfg["scale"] = s
        w, _, _, bh, _, h = self._metrics()
        keep_x = self.root.winfo_x() + self.canvas.winfo_width() // 2
        keep_y = self.root.winfo_y() + self.canvas.winfo_height()
        self.canvas.destroy()
        self._build()
        self._load_images()
        self.root.geometry(f"{w}x{h}+{keep_x - w // 2}+{max(0, keep_y - h)}")
        self._raise_top()
        self.say("greet", hold=4)
        save_cfg(self.cfg)

    def _build_menu(self):
        """菜单单独构建，方便测试，也避免 tk_popup 把逻辑裹在里面。"""
        m = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei", 9))
        m.add_command(label="打开面板（双击我也可以）", command=self.open_panel)
        d = self._today()
        ck = tk.Menu(m, tearoff=0)
        for key, label in CHECKS:
            ck.add_command(label=("✓ " if d.get(key) else "　 ") + label,
                           command=lambda k=key: self.toggle_check(k))
        ck.add_separator()
        ck.add_command(label=f"喝水 +1（{d.get('water', 0)}/8）", command=self.add_water)
        m.add_cascade(label=f"今日打卡 {self.check_done()}/5", menu=ck)
        m.add_separator()
        if self.pomo_end:
            left = max(0, int(self.pomo_end - time.time()))
            m.add_command(label=f"结束专注（还剩 {left // 60:02d}:{left % 60:02d}）", command=self.pomo_stop)
        else:
            sub = tk.Menu(m, tearoff=0)
            for mins in (15, 25, 45):
                sub.add_command(label=f"{mins} 分钟", command=lambda mm=mins: self.pomo_start(mm))
            m.add_cascade(label="开始专注", menu=sub)
        m.add_separator()
        p = tk.Menu(m, tearoff=0)
        for k, name in PERSONA_NAME.items():
            p.add_radiobutton(label=name, value=k, variable=tk.StringVar(value=self.persona),
                              command=lambda kk=k: self.set_persona(kk))
        m.add_cascade(label=f"人格：{PERSONA_NAME[self.persona]}", menu=p)
        s = tk.Menu(m, tearoff=0)
        for label, val in (("小", 0.7), ("中", 0.9), ("大", 1.15)):
            s.add_command(label=label, command=lambda v=val: self.set_scale(v))
        m.add_cascade(label="大小（滚轮也行）", menu=s)
        m.add_checkbutton(label="总在最前", onvalue=1, offvalue=0,
                          variable=tk.IntVar(value=1 if self.cfg.get("topmost") else 0),
                          command=self.toggle_top)
        m.add_checkbutton(label="安静模式", onvalue=1, offvalue=0,
                          variable=tk.IntVar(value=1 if self.quiet else 0),
                          command=self.toggle_quiet)
        m.add_checkbutton(label="开机自启", onvalue=1, offvalue=0,
                          variable=tk.IntVar(value=1 if startup_enabled() else 0),
                          command=self.toggle_startup)
        m.add_command(label="回到右下角", command=self.snap_corner)
        m.add_separator()
        m.add_command(label="退出", command=self.quit)
        return m

    def _menu(self, e):
        m = self._build_menu()
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def toggle_startup(self):
        want = not startup_enabled()
        err = set_startup(want)
        if err:
            self.say("nag", text=f"开机自启没设上：{err}", hold=6)
        else:
            self.say("greet", text="开机自启已打开，下次醒来就能看到我。" if want else "开机自启已关闭。", hold=4)

    def _dbl(self, e):
        if getattr(self, "_click_job", None):
            try: self.root.after_cancel(self._click_job)
            except Exception: pass
            self._click_job = None
        self.open_panel()

    def open_panel(self):
        webbrowser.open(PANEL_URL)
        self.say("praise", text="面板在浏览器里。别只打开不干活。", hold=5)

    def set_persona(self, k):
        self.persona = k
        self.cfg["persona"] = k
        save_cfg(self.cfg)
        self.say("greet")

    def toggle_top(self):
        v = not self.cfg.get("topmost", True)
        self.cfg["topmost"] = v
        self.root.attributes("-topmost", v)
        if v:
            self._raise_top()
        save_cfg(self.cfg)
        self.say("greet", text="我继续压在最上层。" if v else "我退到后面去了，需要我再点一下置顶。", hold=4)

    def toggle_quiet(self):
        self.quiet = not self.quiet
        self.cfg["quiet"] = self.quiet
        save_cfg(self.cfg)
        self.say("greet", text="安静模式：只提醒，不闲聊。" if self.quiet else "话痨模式回来了。", hold=4)

    def snap_corner(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        wx1, wy1, wx2, wy2 = work_area()
        wx2, wy2 = wx2 or sw, wy2 or sh
        w, _, _, _, _, h = self._metrics()
        x, y = wx2 - w - int(36 * self.scale), wy2 - h - int(16 * self.scale)
        self.root.geometry(f"+{x}+{y}")
        self.cfg["x"], self.cfg["y"] = x, y
        save_cfg(self.cfg)

    # ---------------------------------------------------------- 番茄

    # ---------------------------------------------------------- 打卡

    def _today(self):
        key = time.strftime("%Y-%m-%d")
        d = self.cfg.get("daily") or {}
        if d.get("date") != key:
            d = {"date": key, "wake": False, "water": 0,
                 "exercise": False, "read": False, "sleep": False}
            self.cfg["daily"] = d
            save_cfg(self.cfg)
        return d

    def check_done(self):
        d = self._today()
        n = sum(1 for k, _ in CHECKS if d.get(k))
        if int(d.get("water") or 0) >= 8:
            n += 1
        return n

    def toggle_check(self, key):
        d = self._today()
        d[key] = not d.get(key)
        save_cfg(self.cfg)
        label = dict(CHECKS).get(key, key)
        if d[key]:
            self.say("praise", text=f"{label} 记上了。今天第 {self.check_done()} 项。", hold=4, expr="happy")
            beep()
        else:
            self.say("nag", text=f"{label} 撤销了。别自己骗自己。", hold=4, expr="angry")

    def add_water(self):
        d = self._today()
        d["water"] = min(8, int(d.get("water") or 0) + 1)
        save_cfg(self.cfg)
        self.say("water", text=f"第 {d['water']} 杯。喝完继续。", hold=4, expr="happy")
        beep()

    # ---------------------------------------------------------- 番茄

    def pomo_start(self, mins):
        self.pomo_len = mins * 60
        self.pomo_end = time.time() + self.pomo_len
        self.say("greet", text=f"{mins} 分钟，开始。别切窗口。", hold=4, expr="normal")
        beep()

    def pomo_stop(self):
        self.pomo_end = 0
        self.say("greet", text="计时停了。你自己决定要不要继续。", hold=4)

    # ---------------------------------------------------------- 心跳

    def _tick(self):
        now = time.time()
        day = time.strftime("%Y-%m-%d")
        if getattr(self, "_day", day) != day:
            self._day = day
            self._today()
            if not self.line:
                self._show_status()
        self._ticks = getattr(self, "_ticks", 0) + 1

        # 再次双击启动时，第二个实例只会留下一个信号文件，这里负责把自己叫回来
        if os.path.exists(SIGNAL_FILE):
            try:
                os.remove(SIGNAL_FILE)
            except Exception:
                pass
            self.snap_corner()
            self._raise_top()
            self.say("greet", text="我在这儿。别把我弄丢了。", hold=6)
            beep("alert")
        if self._ticks % 25 == 0:
            self._raise_top()
        # 番茄
        if self.pomo_end:
            left = int(self.pomo_end - now)
            if left <= 0:
                self.pomo_end = 0
                self.cfg["pomos"] = int(self.cfg.get("pomos") or 0) + 1
                self.cfg["pomo_date"] = time.strftime("%Y-%m-%d")
                save_cfg(self.cfg)
                self.say("praise", text=f"{self.pomo_len // 60} 分钟到。起来走两步。", hold=9, expr="happy")
                beep("alert")
            else:
                mm, ss = left // 60, left % 60
                self.canvas.itemconfigure(self.cv_text, text=f"专注 {mm:02d}:{ss:02d}")
                self.hold_until = now + 2
        elif now > self.hold_until and self.line:
            self.line = ""
            self._show_status()

        # 定点提醒
        hm = time.strftime("%H:%M")
        key = f"{time.strftime('%Y-%m-%d')} {hm}"
        for t, cat in SCHEDULE:
            if hm == t and self.last_schedule != key:
                self.last_schedule = key
                self.say(cat, hold=10)
                beep("alert")
                break

        # 随机自语
        if not self.quiet and now > self.next_idle and not self.pomo_end:
            self.say("idle", hold=6, silent=True)
            self.next_idle = now + random.randint(300, 900)

        self.root.after(1000, self._tick)

    def _show_status(self):
        hm = time.strftime("%H:%M")
        nxt = ""
        for t, _ in SCHEDULE:
            if t > hm:
                nxt = t
                break
        pomos = self.cfg.get("pomos") if self.cfg.get("pomo_date") == time.strftime("%Y-%m-%d") else 0
        parts = [hm, f"打卡 {self.check_done()}/5"]
        if pomos:
            parts.append(f"番茄 {pomos}")
        if nxt and len(parts) < 3:
            parts.append(f"下次 {nxt}")
        self.canvas.itemconfigure(self.cv_text, text=" · ".join(parts))
        self._set_expr("sleepy" if (int(hm[:2]) >= 23 or int(hm[:2]) < 6) else "normal")

    def _blink_loop(self):
        """没事的时候随机换个表情，别像张壁纸。"""
        now = time.time()
        if not self.pomo_end and now > self.blink_at:
            alt = random.choice(["happy", "sleepy", "angry"])
            self._set_expr(alt)
            self.root.after(900, lambda: self._set_expr(self._idle_expr()))
            self.blink_at = now + random.randint(12, 28)
        self.root.after(1000, self._blink_loop)

    def _idle_expr(self):
        h = int(time.strftime("%H"))
        return "sleepy" if (h >= 23 or h < 6) else "normal"

    # ---------------------------------------------------------- 退出

    def quit(self):
        self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
        save_cfg(self.cfg)
        try:
            self.root.destroy()
        except Exception:
            pass


def main():
    dpi_aware()
    lock = single_instance()
    if lock is None:
        try:
            with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
                f.write("show")
        except Exception:
            pass
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(f"{APP_NAME} · {APP_SUB}",
                            "诺诺已经在桌面上了，我把它叫回右下角了。\n（右键它可以看到菜单）")
        root.destroy()
        return
    pet = DeskPet()
    pet.root.protocol("WM_DELETE_WINDOW", pet.quit)

    def on_err(*args):
        import traceback
        log("CALLBACK ERROR\n" + "".join(traceback.format_exception(*args)))

    pet.root.report_callback_exception = on_err
    log(f"start pid={os.getpid()} scale={pet.scale} persona={pet.persona}")
    try:
        pet.root.mainloop()
    except Exception:
        import traceback
        log("MAINLOOP CRASH\n" + traceback.format_exc())
        raise
    finally:
        log("exit")


if __name__ == "__main__":
    main()
