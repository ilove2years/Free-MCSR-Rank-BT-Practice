import requests
import json
import random
import time
import threading
import queue
import os
import sys
from tkinter import *
from tkinter import scrolledtext, messagebox, filedialog
from pynput import keyboard
from pynput.keyboard import Key, Controller, KeyCode

# ---------------------------- 核心功能函数 ----------------------------
overworld_types = {
    1: "buried_treasure",
    2: "ruined_portal",
    3: "desert_temple",
    4: "village",
    5: "shipwreck",
    6: "random"
}
type_names = {
    1: "宝藏", 2: "废门", 3: "沙漠神殿", 4: "村庄", 5: "沉船", 6: "随机"
}

def fetch_seed(api_base, selected_types):
    """
    从API获取种子，selected_types为选中类型的ID列表（如[1,3,4]）
    若列表为空，则从全部类型中随机选择（包括随机类型）
    返回：(类型ID, 主世界种子, 下界种子)
    """
    if not selected_types:
        # 全不选：从所有类型（包括随机）中随机选
        chosen = random.choice(list(overworld_types.keys()))
    else:
        chosen = random.choice(selected_types)
    # 构造URL
    if chosen == 6:
        # 随机类型：排除6自身，从其他类型中随机选
        other_types = [v for k, v in overworld_types.items() if k != 6]
        chosen_type = random.choice(other_types)
        url = f"{api_base}/api/v2/seed?overworld={chosen_type}&completion=720000"
    else:
        url = f"{api_base}/api/v2/seed?overworld={overworld_types[chosen]}&completion=720000"
    response = requests.get(url)
    data = json.loads(response.text)
    seed_data = data['data']
    return chosen, seed_data['overworldSeed'], seed_data['netherSeed']

def type_text(text, delay=0.01):
    kb = Controller()
    for char in str(text):
        kb.tap(char)
        time.sleep(delay)

def task(api_base, seed_info, log_queue, stats_callback):
    """
    自动化任务函数，直接使用预加载的seed_info
    """
    try:
        chosen_type_id, type_name, owseed, netherseed = seed_info
        log_queue.put(f"使用预加载种子：类型 {type_name}，主世界 {owseed}，下界 {netherseed}")
        kb = Controller()
        # 修正：所有 kb.tab 改为 kb.tap
        kb.tap(Key.tab)
        kb.tap(Key.enter)
        kb.tap(Key.tab)
        kb.tap(Key.tab)
        kb.tap(Key.tab)
        kb.tap(Key.enter)
        kb.tap(Key.tab)
        kb.tap(Key.tab)
        kb.tap(Key.enter)
        kb.tap(Key.enter)
        kb.tap(Key.enter)
        for _ in range(9):
            kb.tap(Key.tab)
        kb.tap(Key.enter)
        for _ in range(4):
            kb.tap(Key.tab)

        type_text(owseed)
        kb.tap(Key.tab)
        time.sleep(0.1)

        type_text(netherseed)
        kb.tap(Key.tab)

        type_text(owseed)

        for _ in range(3):
            kb.tap(Key.tab)
        kb.tap(Key.enter)

        log_queue.put("种子输入完成！")
        stats_callback(type_name, owseed, netherseed)
    except Exception as e:
        log_queue.put(f"任务出错：{str(e)}")

# ---------------------------- GUI界面 ----------------------------
class SeedToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("我的世界种子练习辅助工具")
        self.root.geometry("650x550")
        self.root.resizable(False, False)

        # 配置文件路径
        if getattr(sys, 'frozen', False):
            self.config_path = os.path.join(os.path.dirname(sys.executable), 'config.json')
        else:
            self.config_path = 'config.json'

        # 配置变量
        self.api_base = StringVar(value="http://43.143.231.104:8001")
        self.selected_types = set()
        self.start_hotkey = Key.f5
        self.exit_hotkey = Key.f6
        self.hotkey_capturing = None
        self.stats_count = 0
        self.listener = None
        self.log_queue = queue.Queue()

        # 预加载相关
        self.prefetched_seed = None          # 格式：(类型ID, 类型名称, 主世界种子, 下界种子)
        self.prefetch_lock = threading.Lock()
        self.prefetch_thread = None

        # 创建界面组件
        self.create_widgets()

        # 加载配置文件
        self.load_config()

        # 启动日志处理循环
        self.process_log_queue()

        # 启动全局热键监听
        self.start_listener()

        # 窗口关闭时清理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 初始预加载一次种子
        self.trigger_prefetch()

    def create_widgets(self):
        # ---------- API设置 ----------
        frame_api = LabelFrame(self.root, text="API设置", padx=5, pady=5)
        frame_api.pack(fill="x", padx=10, pady=5)

        Label(frame_api, text="API地址:").grid(row=0, column=0, sticky=W)
        Entry(frame_api, textvariable=self.api_base, width=50).grid(row=0, column=1, padx=5)
        Label(frame_api, text="默认: http://43.143.231.104:8001", fg="gray").grid(row=1, column=0, columnspan=2, sticky=W)

        # ---------- 开局类型选择 ----------
        frame_type = LabelFrame(self.root, text="开局类型选择（可多选，全不选则为全部随机）", padx=5, pady=5)
        frame_type.pack(fill="x", padx=10, pady=5)

        self.type_vars = {}
        for i in range(1, 7):
            var = IntVar()
            cb = Checkbutton(frame_type, text=type_names[i], variable=var, command=self.on_type_change)
            cb.grid(row=(i-1)//3, column=(i-1)%3, sticky=W)
            self.type_vars[i] = var

        btn_frame = Frame(frame_type)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=5)
        Button(btn_frame, text="全选", command=self.select_all).pack(side=LEFT, padx=5)
        Button(btn_frame, text="全不选", command=self.select_none).pack(side=LEFT, padx=5)

        # ---------- 热键设置 ----------
        frame_hotkey = LabelFrame(self.root, text="热键设置（点击按钮后按下任意键）", padx=5, pady=5)
        frame_hotkey.pack(fill="x", padx=10, pady=5)

        Label(frame_hotkey, text="启动热键:").grid(row=0, column=0, sticky=W)
        self.btn_start_hotkey = Button(frame_hotkey, text="F5", width=10, command=lambda: self.capture_hotkey('start'))
        self.btn_start_hotkey.grid(row=0, column=1, padx=5)

        Label(frame_hotkey, text="退出热键:").grid(row=0, column=2, sticky=W, padx=(20,0))
        self.btn_exit_hotkey = Button(frame_hotkey, text="F6", width=10, command=lambda: self.capture_hotkey('exit'))
        self.btn_exit_hotkey.grid(row=0, column=3, padx=5)

        # 保存热键的原始文本（用于恢复）
        self.start_hotkey_text = StringVar(value="F5")
        self.exit_hotkey_text = StringVar(value="F6")

        # ---------- 当前种子信息 ----------
        frame_info = LabelFrame(self.root, text="当前种子信息", padx=5, pady=5)
        frame_info.pack(fill="x", padx=10, pady=5)

        self.info_text = StringVar()
        self.info_text.set("类型：--\n主世界种子：--\n下界种子：--")
        Label(frame_info, textvariable=self.info_text, justify=LEFT).pack(anchor=W)

        self.count_label = Label(frame_info, text="已筛选种子数：0")
        self.count_label.pack(anchor=W, pady=2)

        # 预加载状态显示
        self.prefetch_label = Label(frame_info, text="预加载状态：空闲", fg="blue")
        self.prefetch_label.pack(anchor=W, pady=2)

        # ---------- 日志窗口（带按钮）----------
        frame_log = LabelFrame(self.root, text="操作日志", padx=5, pady=5)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        # 按钮行
        btn_log_frame = Frame(frame_log)
        btn_log_frame.pack(fill="x", pady=2)
        Button(btn_log_frame, text="清空日志", command=self.clear_log).pack(side=LEFT, padx=2)
        Button(btn_log_frame, text="导出日志", command=self.export_log).pack(side=LEFT, padx=2)

        self.log_area = scrolledtext.ScrolledText(frame_log, height=8, state='disabled')
        self.log_area.pack(fill="both", expand=True)

    # ---------- 类型选择变化处理 ----------
    def on_type_change(self):
        self.update_selected_types()
        self.save_config()          # 保存设置
        self.trigger_prefetch()     # 触发预加载新种子

    def update_selected_types(self):
        self.selected_types.clear()
        for tid, var in self.type_vars.items():
            if var.get() == 1:
                self.selected_types.add(tid)

    def select_all(self):
        for var in self.type_vars.values():
            var.set(1)
        self.on_type_change()

    def select_none(self):
        for var in self.type_vars.values():
            var.set(0)
        self.on_type_change()

    # ---------- 预加载机制 ----------
    def trigger_prefetch(self):
        """启动预加载线程（如果已有正在运行的则等待后重试）"""
        with self.prefetch_lock:
            if self.prefetch_thread and self.prefetch_thread.is_alive():
                self.log_queue.put("预加载正在进行，稍后重新尝试...")
                self.root.after(1000, self.trigger_prefetch)  # 1秒后重试
                return
            self.prefetch_thread = threading.Thread(target=self._prefetch_worker, daemon=True)
            self.prefetch_thread.start()

    def _prefetch_worker(self):
        """后台预加载种子，成功时更新界面显示"""
        self.root.after(0, lambda: self.prefetch_label.config(text="预加载状态：正在获取...", fg="orange"))
        api_base = self.api_base.get().rstrip('/')
        selected = list(self.selected_types)  # 如果为空，fetch_seed会处理为全部随机
        try:
            tid, ow, nether = fetch_seed(api_base, selected)
            tname = type_names[tid]
            with self.prefetch_lock:
                self.prefetched_seed = (tid, tname, ow, nether)
            # 更新界面显示种子信息（不增加计数）
            self.root.after(0, self.update_display_with_seed, tname, ow, nether)
            self.root.after(0, lambda: self.prefetch_label.config(
                text=f"预加载状态：就绪 ({tname})", fg="green"))
            self.log_queue.put(f"预加载成功：{tname} - {ow}")
        except Exception as e:
            self.root.after(0, lambda: self.prefetch_label.config(
                text="预加载状态：失败", fg="red"))
            self.log_queue.put(f"预加载失败：{str(e)}")

    def update_display_with_seed(self, type_name, owseed, netherseed):
        """仅更新种子信息显示，不增加计数"""
        self.info_text.set(
            f"类型：{type_name}\n主世界种子：{owseed}\n下界种子：{netherseed}"
        )

    # ---------- 热键捕获 ----------
    def capture_hotkey(self, hotkey_type):
        self.hotkey_capturing = hotkey_type
        btn = self.btn_start_hotkey if hotkey_type == 'start' else self.btn_exit_hotkey
        btn.config(text="按下任意键...", relief=SUNKEN)
        self.capture_listener = keyboard.Listener(on_press=self.on_capture_press)
        self.capture_listener.start()

    def on_capture_press(self, key):
        if self.capture_listener:
            self.capture_listener.stop()
        self.root.after(0, self.set_hotkey, key)
        return False

    def set_hotkey(self, key):
        if self.hotkey_capturing == 'start':
            self.start_hotkey = key
            btn_text = self.key_to_str(key)
            self.btn_start_hotkey.config(text=btn_text, relief=RAISED)
            self.start_hotkey_text.set(btn_text)
        elif self.hotkey_capturing == 'exit':
            self.exit_hotkey = key
            btn_text = self.key_to_str(key)
            self.btn_exit_hotkey.config(text=btn_text, relief=RAISED)
            self.exit_hotkey_text.set(btn_text)
        self.hotkey_capturing = None
        self.save_config()
        self.restart_listener()

    def key_to_str(self, key):
        if hasattr(key, 'char') and key.char is not None:
            return key.char.upper()
        elif hasattr(key, 'name'):
            return key.name.upper()
        else:
            return str(key)

    def str_to_key(self, s):
        if len(s) == 1:
            return KeyCode.from_char(s.lower())
        else:
            try:
                return getattr(Key, s.lower())
            except AttributeError:
                return Key.f5

    # ---------- 配置文件读写 ----------
    def save_config(self):
        config = {
            'api_base': self.api_base.get(),
            'selected_types': list(self.selected_types),
            'start_hotkey': self.start_hotkey_text.get(),
            'exit_hotkey': self.exit_hotkey_text.get()
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log_queue.put(f"保存配置失败：{e}")

    def load_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if 'api_base' in config:
                self.api_base.set(config['api_base'])
            selected = config.get('selected_types', [])
            for tid in selected:
                if tid in self.type_vars:
                    self.type_vars[tid].set(1)
            self.update_selected_types()
            if 'start_hotkey' in config:
                self.start_hotkey = self.str_to_key(config['start_hotkey'])
                self.btn_start_hotkey.config(text=config['start_hotkey'])
                self.start_hotkey_text.set(config['start_hotkey'])
            if 'exit_hotkey' in config:
                self.exit_hotkey = self.str_to_key(config['exit_hotkey'])
                self.btn_exit_hotkey.config(text=config['exit_hotkey'])
                self.exit_hotkey_text.set(config['exit_hotkey'])
        except Exception as e:
            self.log_queue.put(f"加载配置失败：{e}")

    # ---------- 热键监听 ----------
    def start_listener(self):
        def on_press(key):
            if key == self.start_hotkey:
                threading.Thread(target=self.run_task, daemon=True).start()
            elif key == self.exit_hotkey:
                self.root.after(0, self.on_closing)

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def restart_listener(self):
        if self.listener:
            self.listener.stop()
        self.start_listener()

    # ---------- 任务执行 ----------
    def run_task(self):
        api_base = self.api_base.get().rstrip('/')
        with self.prefetch_lock:
            if self.prefetched_seed is not None:
                seed_info = self.prefetched_seed
                self.prefetched_seed = None
                self.log_queue.put("使用预加载种子开始任务...")
                task(api_base, seed_info, self.log_queue, self.update_stats)
                self.root.after(0, self.trigger_prefetch)
            else:
                self.log_queue.put("没有预加载种子，将实时获取...")
                try:
                    selected = list(self.selected_types)
                    tid, ow, nether = fetch_seed(api_base, selected)
                    tname = type_names[tid]
                    seed_info = (tid, tname, ow, nether)
                    task(api_base, seed_info, self.log_queue, self.update_stats)
                except Exception as e:
                    self.log_queue.put(f"实时获取种子失败：{e}")
                finally:
                    self.root.after(0, self.trigger_prefetch)

    def update_stats(self, type_name, owseed, netherseed):
        self.stats_count += 1
        self.info_text.set(
            f"类型：{type_name}\n主世界种子：{owseed}\n下界种子：{netherseed}"
        )
        self.count_label.config(text=f"已筛选种子数：{self.stats_count}")

    # ---------- 日志管理 ----------
    def clear_log(self):
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, END)
        self.log_area.config(state='disabled')

    def export_log(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                   filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if file_path:
            try:
                content = self.log_area.get(1.0, END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("导出成功", f"日志已保存到：{file_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"保存文件时出错：{e}")

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_area.config(state='normal')
                self.log_area.insert(END, msg + "\n")
                self.log_area.see(END)
                self.log_area.config(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

    def on_closing(self):
        if self.listener:
            self.listener.stop()
        self.save_config()
        self.root.destroy()

if __name__ == "__main__":
    root = Tk()
    app = SeedToolGUI(root)
    root.mainloop()
