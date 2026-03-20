import requests
import json
import random
import time
import threading
import queue
import os
import sys
import traceback
from tkinter import *
from tkinter import scrolledtext, messagebox, filedialog, ttk

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

# 下界堡垒类型映射
nether_types = {
    "bridge": "桥",
    "treasure": "藏宝室",
    "housing": "居住区",
    "stable": "棚"
}

# 变种数据结构（按分类分组）- 新增 fortress 分类
variations_data = {
    "overworld": {
        "village": [
            "biome:structure:desert",
            "biome:structure:plains",
            "biome:structure:savanna",
            "biome:structure:snowy_tundra",
            "biome:structure:taiga",
            "chest:structure:diamond",
            "chest:structure:obsidian"
        ],
        "desert_temple": [
            "chest:structure:diamond",
            "chest:structure:egap"
        ],
        "ruined_portal": [
            "chest:structure:egap",
            "chest:structure:golden_carrot",
            "chest:structure:looting_sword",
            "type:structure:completable",
            "type:structure:lava"
        ],
        "shipwreck": [
            "chest:structure:carrot",
            "chest:structure:diamond",
            "type:structure:normal",
            "type:structure:sideways",
            "type:structure:upsidedown"
        ],
        "buried_treasure": []  # 无变种
    },
    "bastion": {
        "bridge": [
            "bastion:single:1",
            "bastion:single:2",
            "bastion:triple:1",
            "bastion:triple:2"
        ],
        "treasure": [],
        "housing": [
            "bastion:single:1",
            "bastion:triple:1",
            "bastion:triple:2"
        ],
        "stable": [
            "bastion:good_gap:1",
            "bastion:good_gap:2",
            "bastion:single:1",
            "bastion:single:2",
            "bastion:single:3",
            "bastion:small_single:1",
            "bastion:small_single:2",
            "bastion:small_single:3",
            "bastion:triple:1",
            "bastion:triple:2",
            "bastion:triple:3"
        ]
    },
    "fortress": {
        "fortress": [
            "biome:fortress:basalt_deltas",
            "biome:fortress:crimson_forest",
            "biome:fortress:nether_wastes",
            "biome:fortress:soul_sand_valley",
            "biome:fortress:warped_forest"
        ]
    },
    "end": {
        "end_tower": [
            "end_tower:caged:back",
            "end_tower:caged:back_center",
            "end_tower:caged:front",
            "end_tower:caged:front_center"
        ],
        "end_spawn": ["end_spawn:buried"]
    }
}

def fetch_seed(api_base, selected_overworld, selected_nether, selected_variations, completion_ms):
    """从API获取种子，支持多条件筛选"""
    if not selected_overworld:
        overworld_choice = random.choice(list(overworld_types.keys()))
    else:
        overworld_choice = random.choice(selected_overworld)

    if selected_nether:
        nether_choice = random.choice(selected_nether)
    else:
        nether_choice = None

    url = f"{api_base}/api/v2/seed?overworld={overworld_types[overworld_choice]}"
    if nether_choice:
        url += f"&nether={nether_choice}"

    if selected_variations:
        allowed_vars = list(selected_variations)
        if allowed_vars:
            url += "&variations=" + ",".join(allowed_vars)

    if completion_ms:
        url += f"&completion={completion_ms}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            error_msg = response.text[:200] if response.text else "无响应内容"
            raise Exception(f"API返回HTTP {response.status_code}：{error_msg}")
        data = response.json()
        if not data.get('success'):
            raise Exception(f"API返回错误：{data.get('message', '未知错误')}")
        seed_data = data['data']
        return (overworld_choice, type_names[overworld_choice],
                seed_data['overworldSeed'], seed_data['netherSeed'],
                seed_data.get('availableCounts', 0))
    except Exception as e:
        raise Exception(f"获取种子失败：{str(e)}")

def type_text(text, delay=0.01):
    from pynput.keyboard import Controller
    kb = Controller()
    for char in str(text):
        kb.tap(char)
        time.sleep(delay)

def task(api_base, seed_info, log_queue, stats_callback):
    """自动化任务函数"""
    try:
        chosen_type_id, type_name, owseed, netherseed = seed_info
        log_queue.put(f"使用预加载种子：类型 {type_name}，主世界 {owseed}，下界 {netherseed}")
        from pynput.keyboard import Key, Controller
        kb = Controller()
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
        log_queue.put(traceback.format_exc())

# ---------------------------- GUI界面 ----------------------------
class SeedToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("一键导入Ranked种子promax版")
        self.root.geometry("1000x600")
        self.root.resizable(True, True)

        if getattr(sys, 'frozen', False):
            self.config_path = os.path.join(os.path.dirname(sys.executable), 'config.json')
        else:
            self.config_path = 'config.json'

        self.default_api = "http://43.143.231.104:8001"
        self.api_base = StringVar(value=self.default_api)
        self.selected_overworld = set()
        self.selected_nether = set()
        self.selected_variations = set()
        from pynput.keyboard import Key
        self.start_hotkey = Key.f5
        self.exit_hotkey = Key.f6
        self.hotkey_capturing = None
        self.stats_count = 0
        self.listener = None
        self.log_queue = queue.Queue()

        self.prefetched_seed = None
        self.prefetch_lock = threading.Lock()
        self.prefetch_thread = None
        self.last_available_counts = 0
        self.prefetch_fail_count = 0  # 失败计数

        self.completion_min = StringVar(value="")
        self.completion_sec = StringVar(value="")
        self.variation_text = StringVar(value="")

        self.use_elo = BooleanVar(value=False)
        self.elo_option = StringVar(value="1200+")
        self.custom_weights = {1: IntVar(value=20), 2: IntVar(value=20), 3: IntVar(value=20),
                               4: IntVar(value=20), 5: IntVar(value=20)}
        self.weight_total = IntVar(value=100)
        self.weight_debounce_id = None  # 用于防抖

        self.create_main_layout()
        self.load_config()
        self.process_log_queue()
        self.start_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.trigger_prefetch()

    def create_main_layout(self):
        main_pane = PanedWindow(self.root, orient=HORIZONTAL)
        main_pane.pack(fill=BOTH, expand=True)

        left_frame = Frame(main_pane, width=650)
        main_pane.add(left_frame, width=650)

        self.left_canvas = Canvas(left_frame, borderwidth=0, highlightthickness=0)
        scrollbar = Scrollbar(left_frame, orient=VERTICAL, command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.left_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.left_interior = Frame(self.left_canvas)
        self.left_canvas.create_window((0, 0), window=self.left_interior, anchor=NW)
        self.left_interior.bind("<Configure>", self._on_left_configure)

        right_frame = Frame(main_pane, width=350)
        main_pane.add(right_frame, width=350)
        self.create_log_panel(right_frame)

        self.create_control_panels()

    def _on_left_configure(self, event):
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

    def create_control_panels(self):
        parent = self.left_interior

        # API设置
        frame_api = LabelFrame(parent, text="API设置", padx=5, pady=5)
        frame_api.pack(fill="x", padx=10, pady=5)
        Label(frame_api, text="API地址:").grid(row=0, column=0, sticky=W)
        self.api_entry = Entry(frame_api, textvariable=self.api_base, width=50)
        self.api_entry.grid(row=0, column=1, padx=5)
        Label(frame_api, text="默认: http://43.143.231.104:8001", fg="gray").grid(row=1, column=0, columnspan=2, sticky=W)

        def on_api_entry_change(event=None):
            current = self.api_base.get().strip()
            if not current:
                self.api_base.set(self.default_api)
                self.log_queue.put(f"API地址已重置为默认：{self.default_api}")

        self.api_entry.bind("<KeyRelease>", on_api_entry_change)

        # 开局类型选择
        self.frame_type = LabelFrame(parent, text="开局（全不选则为全部随机）", padx=5, pady=5)
        self.frame_type.pack(fill="x", padx=10, pady=5)
        self.type_vars = {}
        for i in range(1, 6):
            var = IntVar()
            cb = Checkbutton(self.frame_type, text=type_names[i], variable=var, command=self.on_overworld_change)
            cb.grid(row=(i-1)//3, column=(i-1)%3, sticky=W)
            self.type_vars[i] = var
        self.random_var = IntVar()
        cb_random = Checkbutton(self.frame_type, text=type_names[6], variable=self.random_var, command=self.on_overworld_change)
        cb_random.grid(row=1, column=2, sticky=W)

        btn_frame = Frame(self.frame_type)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=5)
        Button(btn_frame, text="全选", command=self.select_all_overworld).pack(side=LEFT, padx=5)
        Button(btn_frame, text="全不选", command=self.select_none_overworld).pack(side=LEFT, padx=5)

        # Elo权重设置
        frame_elo = LabelFrame(parent, text="使用官方elo权重", padx=5, pady=5)
        frame_elo.pack(fill="x", padx=10, pady=5)
        self.elo_check = Checkbutton(frame_elo, text="启用Elo权重", variable=self.use_elo, command=self.on_elo_toggle)
        self.elo_check.grid(row=0, column=0, columnspan=4, sticky=W)
        self.elo_radio_frame = Frame(frame_elo)
        self.elo_radio_frame.grid(row=1, column=0, columnspan=4, sticky=W, pady=5)
        Radiobutton(self.elo_radio_frame, text="1200+", variable=self.elo_option, value="1200+", command=self.on_elo_option_change).pack(side=LEFT, padx=2)
        Radiobutton(self.elo_radio_frame, text="600-1200", variable=self.elo_option, value="600-1200", command=self.on_elo_option_change).pack(side=LEFT, padx=2)
        Radiobutton(self.elo_radio_frame, text="0-599", variable=self.elo_option, value="0-599", command=self.on_elo_option_change).pack(side=LEFT, padx=2)
        Radiobutton(self.elo_radio_frame, text="自定义", variable=self.elo_option, value="自定义", command=self.on_elo_option_change).pack(side=LEFT, padx=2)

        self.custom_frame = Frame(frame_elo)
        self.custom_frame.grid(row=2, column=0, columnspan=4, pady=5, sticky=W)
        self.weight_sliders = {}
        types_order = [1,2,3,4,5]
        for i, tid in enumerate(types_order):
            Label(self.custom_frame, text=type_names[tid]).grid(row=0, column=i*2)
            slider = Scale(self.custom_frame, from_=0, to=100, orient=HORIZONTAL, variable=self.custom_weights[tid], length=80, command=self.on_weight_slider_change)
            slider.grid(row=1, column=i*2)
            self.weight_sliders[tid] = slider
        Label(self.custom_frame, text="总和:").grid(row=2, column=0)
        Label(self.custom_frame, textvariable=self.weight_total).grid(row=2, column=1, sticky=W)
        Button(self.custom_frame, text="均衡", command=self.balance_weights).grid(row=2, column=2, columnspan=4)

        self.update_elo_state()

        # 热键设置
        frame_hotkey = LabelFrame(parent, text="热键设置（点击按钮后按下任意键）", padx=5, pady=5)
        frame_hotkey.pack(fill="x", padx=10, pady=5)
        Label(frame_hotkey, text="启动热键:").grid(row=0, column=0, sticky=W)
        self.btn_start_hotkey = Button(frame_hotkey, text="F5", width=8, command=lambda: self.capture_hotkey('start'))
        self.btn_start_hotkey.grid(row=0, column=1, padx=5)
        Label(frame_hotkey, text="退出热键:").grid(row=0, column=2, sticky=W, padx=(20,0))
        self.btn_exit_hotkey = Button(frame_hotkey, text="F6", width=8, command=lambda: self.capture_hotkey('exit'))
        self.btn_exit_hotkey.grid(row=0, column=3, padx=5)
        self.start_hotkey_text = StringVar(value="F5")
        self.exit_hotkey_text = StringVar(value="F6")

        # 当前种子信息
        frame_info = LabelFrame(parent, text="当前种子信息", padx=5, pady=5)
        frame_info.pack(fill="x", padx=10, pady=5)
        self.info_text = StringVar()
        self.info_text.set("类型：--\n主世界种子：--\n下界种子：--")
        Label(frame_info, textvariable=self.info_text, justify=LEFT).pack(anchor=W)
        self.count_label = Label(frame_info, text="已筛选种子数：0")
        self.count_label.pack(anchor=W, pady=2)
        self.available_label = Label(frame_info, text="可用种子数：--")
        self.available_label.pack(anchor=W, pady=2)
        self.prefetch_label = Label(frame_info, text="预加载状态：空闲", fg="blue")
        self.prefetch_label.pack(anchor=W, pady=2)

        # 高级/百宝箱切换
        btn_frame_toggle = Frame(parent)
        btn_frame_toggle.pack(fill="x", padx=10, pady=5)
        self.btn_advanced = Button(btn_frame_toggle, text="▼ 高级设置", command=self.toggle_advanced)
        self.btn_advanced.pack(side=LEFT, padx=5)
        self.btn_toolbox = Button(btn_frame_toggle, text="▼ 百宝箱", command=self.toggle_toolbox)
        self.btn_toolbox.pack(side=LEFT, padx=5)

        self.frame_advanced = LabelFrame(parent, text="高级设置", padx=5, pady=5)
        self.create_advanced_panel()
        self.frame_advanced.pack(fill="x", padx=10, pady=5)
        self.frame_advanced.pack_forget()

        self.frame_toolbox = LabelFrame(parent, text="百宝箱", padx=5, pady=5)
        self.create_toolbox_panel()
        self.frame_toolbox.pack(fill="x", padx=10, pady=5)
        self.frame_toolbox.pack_forget()

        # 底部警告
        warning_frame = Frame(parent)
        warning_frame.pack(fill="x", padx=10, pady=10)
        warning_label = Label(warning_frame, text="⚠ 切勿在非游戏主界面处按下启动热键，否则可能会出现很严重的后果。",
                              fg="red", font=("微软雅黑", 9), wraplength=600, justify=LEFT)
        warning_label.pack()

    def create_log_panel(self, parent):
        frame_log = LabelFrame(parent, text="操作日志", padx=5, pady=5)
        frame_log.pack(fill="both", expand=True, padx=5, pady=5)
        btn_log_frame = Frame(frame_log)
        btn_log_frame.pack(fill="x", pady=2)
        Button(btn_log_frame, text="清空日志", command=self.clear_log).pack(side=LEFT, padx=2)
        Button(btn_log_frame, text="导出日志", command=self.export_log).pack(side=LEFT, padx=2)
        self.log_area = scrolledtext.ScrolledText(frame_log, height=20, state='disabled')
        self.log_area.pack(fill="both", expand=True)

    def create_advanced_panel(self):
        self.var_checkboxes = {}
        frame_nether = LabelFrame(self.frame_advanced, text="下界堡垒类型（可多选）", padx=5, pady=5)
        frame_nether.pack(fill="x", pady=2)
        self.nether_vars = {}
        for i, (key, name) in enumerate(nether_types.items()):
            var = IntVar()
            cb = Checkbutton(frame_nether, text=name, variable=var, command=self.on_nether_change)
            cb.grid(row=0, column=i, padx=5)
            self.nether_vars[key] = var

        frame_variations = LabelFrame(self.frame_advanced, text="变种（仅当对应主世界/下界被选中时生效）", padx=5, pady=5)
        frame_variations.pack(fill="both", expand=True, pady=2)

        self.var_notebook = ttk.Notebook(frame_variations)
        self.var_notebook.pack(fill="both", expand=True)

        self.overworld_var_frame = Frame(self.var_notebook)
        self.var_notebook.add(self.overworld_var_frame, text="主世界")
        self.create_variation_group(self.overworld_var_frame, "overworld")

        self.bastion_var_frame = Frame(self.var_notebook)
        self.var_notebook.add(self.bastion_var_frame, text="下界堡垒")
        self.create_variation_group(self.bastion_var_frame, "bastion")

        self.fortress_var_frame = Frame(self.var_notebook)
        self.var_notebook.add(self.fortress_var_frame, text="下界要塞")
        self.create_variation_group(self.fortress_var_frame, "fortress")

        self.end_var_frame = Frame(self.var_notebook)
        self.var_notebook.add(self.end_var_frame, text="末地")
        self.create_variation_group(self.end_var_frame, "end")

        frame_extra = Frame(frame_variations)
        frame_extra.pack(fill="x", pady=2)
        Label(frame_extra, text="其他变种（逗号分隔）:").pack(side=LEFT)
        Entry(frame_extra, textvariable=self.variation_text, width=40).pack(side=LEFT, padx=5)
        Button(frame_extra, text="清除", command=lambda: self.variation_text.set("")).pack(side=LEFT)

        frame_time = LabelFrame(self.frame_advanced, text="完成时间上限（留空表示不限制）", padx=5, pady=5)
        frame_time.pack(fill="x", pady=2)
        Label(frame_time, text="分钟:").grid(row=0, column=0)
        Spinbox(frame_time, from_=0, to=59, textvariable=self.completion_min, width=5).grid(row=0, column=1)
        Label(frame_time, text="秒:").grid(row=0, column=2, padx=(10,0))
        Spinbox(frame_time, from_=0, to=59, textvariable=self.completion_sec, width=5).grid(row=0, column=3)

    def create_variation_group(self, parent, category):
        row = 0
        col = 0
        data = variations_data[category]
        for struct_type, vars_list in data.items():
            if not vars_list:
                continue
            frame = LabelFrame(parent, text=struct_type, padx=3, pady=3)
            frame.grid(row=row, column=col, sticky=NW, padx=5, pady=5)
            for idx, var_str in enumerate(vars_list):
                var = IntVar()
                cb = Checkbutton(frame, text=var_str, variable=var, command=self.on_variation_change)
                cb.grid(row=idx, column=0, sticky=W)
                self.var_checkboxes[var_str] = var
            Button(frame, text="清除", command=lambda vs=vars_list: self.clear_variation_group(vs)).grid(row=len(vars_list), column=0, pady=2)
            col += 1
            if col > 2:
                col = 0
                row += 1

    def clear_variation_group(self, var_strings):
        for s in var_strings:
            if s in self.var_checkboxes:
                self.var_checkboxes[s].set(0)
        self.on_variation_change()

    def create_toolbox_panel(self):
        frame = Frame(self.frame_toolbox)
        frame.pack(fill="x", pady=5, padx=5)

        self.match_result_text = StringVar()
        self.match_result_text.set("")

        row1 = Frame(frame)
        row1.pack(fill="x", pady=2)
        Label(row1, text="比赛ID:").pack(side=LEFT)
        self.match_id_entry = Entry(row1, width=15)
        self.match_id_entry.pack(side=LEFT, padx=5)
        Button(row1, text="查询", command=self.query_match).pack(side=LEFT)

        self.match_result_message = Message(frame, textvariable=self.match_result_text, width=300, justify=LEFT, fg="blue")
        self.match_result_message.pack(fill="x", pady=5)

        Button(frame, text="导入到基本界面", command=self.import_match).pack(pady=5)
        warning_label = Label(frame, text="注意：因种子值查询失败，仅导入结构和变种，可能导致筛选条件过于严格。若预加载报错，请检查高级设置。",
                              fg="red", wraplength=280, justify=LEFT)
        warning_label.pack(pady=5)

    # ---------- Elo权重相关 ----------
    def on_elo_toggle(self):
        self.update_elo_state()
        self.save_config()
        self.trigger_prefetch()

    def update_elo_state(self):
        enabled = self.use_elo.get()
        for var in self.type_vars.values():
            if enabled:
                var.set(0)
        for cb in self.frame_type.winfo_children():
            if isinstance(cb, Checkbutton):
                cb.config(state=DISABLED if enabled else NORMAL)
        for cb in self.frame_type.winfo_children():
            if isinstance(cb, Checkbutton) and cb.cget("text") == "随机":
                cb.config(state=DISABLED if enabled else NORMAL)
                break

        if enabled:
            self.elo_radio_frame.grid()
            self.on_elo_option_change()
        else:
            self.elo_radio_frame.grid_remove()
            self.custom_frame.grid_remove()

    def on_elo_option_change(self):
        if not self.use_elo.get():
            return
        option = self.elo_option.get()
        if option == "1200+":
            weights = {1:20, 2:20, 3:20, 4:20, 5:20}
            self.custom_frame.grid_remove()
        elif option == "600-1200":
            weights = {1:0, 2:20, 3:25, 4:30, 5:25}
            self.custom_frame.grid_remove()
        elif option == "0-599":
            weights = {1:0, 2:0, 3:30, 4:55, 5:15}  # 宝藏废门权重为0
            self.custom_frame.grid_remove()
        else:  # 自定义
            self.custom_frame.grid()
            self.update_weight_total()
            return

        for tid, val in weights.items():
            self.custom_weights[tid].set(val)
        self.update_weight_total()
        self.save_config()
        self.trigger_prefetch()

    def on_weight_slider_change(self, value):
        self.update_weight_total()
        # 防抖：延迟0.5秒后保存和预加载
        if self.weight_debounce_id:
            self.root.after_cancel(self.weight_debounce_id)
        self.weight_debounce_id = self.root.after(500, self._delayed_weight_action)

    def _delayed_weight_action(self):
        self.save_config()
        self.trigger_prefetch()
        self.weight_debounce_id = None

    def balance_weights(self):
        total = sum(self.custom_weights[tid].get() for tid in range(1,6))
        if total == 0:
            for tid in range(1,6):
                self.custom_weights[tid].set(20)
        else:
            factor = 100 / total
            for tid in range(1,6):
                self.custom_weights[tid].set(round(self.custom_weights[tid].get() * factor))
        self.update_weight_total()
        self.save_config()
        self.trigger_prefetch()

    def update_weight_total(self):
        total = sum(self.custom_weights[tid].get() for tid in range(1,6))
        self.weight_total.set(total)

    # ---------- 事件处理 ----------
    def on_overworld_change(self):
        self.update_selected_overworld()
        self.save_config()
        self.trigger_prefetch()

    def update_selected_overworld(self):
        self.selected_overworld.clear()
        for tid, var in self.type_vars.items():
            if var.get() == 1:
                self.selected_overworld.add(tid)
        if self.random_var.get() == 1:
            self.selected_overworld.clear()
            for var in self.type_vars.values():
                var.set(0)
            self.random_var.set(1)

    def select_all_overworld(self):
        for var in self.type_vars.values():
            var.set(1)
        self.random_var.set(0)
        self.on_overworld_change()

    def select_none_overworld(self):
        for var in self.type_vars.values():
            var.set(0)
        self.random_var.set(0)
        self.on_overworld_change()

    def on_nether_change(self):
        self.update_selected_nether()
        self.save_config()
        self.trigger_prefetch()

    def update_selected_nether(self):
        self.selected_nether.clear()
        for key, var in self.nether_vars.items():
            if var.get() == 1:
                self.selected_nether.add(key)

    def on_variation_change(self):
        self.update_selected_variations()
        self.save_config()
        self.trigger_prefetch()

    def update_selected_variations(self):
        self.selected_variations.clear()
        for var_str, var in self.var_checkboxes.items():
            if var.get() == 1:
                self.selected_variations.add(var_str)
        extra = self.variation_text.get().strip()
        if extra:
            for v in extra.split(','):
                v = v.strip()
                if v:
                    self.selected_variations.add(v)

    # ---------- 高级/百宝箱切换 ----------
    def toggle_advanced(self):
        if self.frame_advanced.winfo_ismapped():
            self.frame_advanced.pack_forget()
            self.btn_advanced.config(text="▼ 高级设置")
        else:
            self.frame_advanced.pack(fill="x", padx=10, pady=5, after=self.btn_advanced.master)
            self.btn_advanced.config(text="▲ 高级设置")
            if self.frame_toolbox.winfo_ismapped():
                self.frame_toolbox.pack_forget()
                self.btn_toolbox.config(text="▼ 百宝箱")

    def toggle_toolbox(self):
        if self.frame_toolbox.winfo_ismapped():
            self.frame_toolbox.pack_forget()
            self.btn_toolbox.config(text="▼ 百宝箱")
        else:
            self.frame_toolbox.pack(fill="x", padx=10, pady=5, after=self.btn_advanced.master)
            self.btn_toolbox.config(text="▲ 百宝箱")
            if self.frame_advanced.winfo_ismapped():
                self.frame_advanced.pack_forget()
                self.btn_advanced.config(text="▼ 高级设置")

    # ---------- 预加载（改进版：失败计数和退避）----------
    def trigger_prefetch(self):
        with self.prefetch_lock:
            if self.prefetch_thread and self.prefetch_thread.is_alive():
                self.log_queue.put("预加载正在进行，稍后重新尝试...")
                self.root.after(3000, self.trigger_prefetch)
                return
            self.prefetch_fail_count = 0
            self.prefetch_thread = threading.Thread(target=self._prefetch_worker, daemon=True)
            self.prefetch_thread.start()

    def _prefetch_worker(self):
        self.root.after(0, lambda: self.prefetch_label.config(text="预加载状态：正在获取...", fg="orange"))
        api_base = self.api_base.get().rstrip('/')

        # 根据Elo确定主世界类型列表
        if self.use_elo.get():
            option = self.elo_option.get()
            if option == "自定义":
                # 自定义权重：仅选择权重 > 0 的类型
                possible_types = [tid for tid in range(1,6) if self.custom_weights[tid].get() > 0]
                if possible_types:
                    weights = [self.custom_weights[tid].get() for tid in possible_types]
                    overworld_choice = random.choices(possible_types, weights=weights)[0]
                    selected_overworld_list = [overworld_choice]
                else:
                    # 所有权重为0，则从全部类型随机
                    selected_overworld_list = list(range(1,6))
            else:
                # 预设权重：直接使用 self.custom_weights 中的值
                possible_types = [tid for tid in range(1,6) if self.custom_weights[tid].get() > 0]
                if possible_types:
                    weights = [self.custom_weights[tid].get() for tid in possible_types]
                    overworld_choice = random.choices(possible_types, weights=weights)[0]
                    selected_overworld_list = [overworld_choice]
                else:
                    selected_overworld_list = list(range(1,6))
        else:
            selected_overworld_list = list(self.selected_overworld)

        selected_nether_list = list(self.selected_nether)
        self.update_selected_variations()
        completion_ms = None
        if self.completion_min.get() or self.completion_sec.get():
            try:
                minutes = int(self.completion_min.get() or 0)
                seconds = int(self.completion_sec.get() or 0)
                completion_ms = (minutes * 60 + seconds) * 1000
            except:
                completion_ms = None

        try:
            tid, tname, ow, nether, avail = fetch_seed(api_base, selected_overworld_list, selected_nether_list,
                                                       self.selected_variations, completion_ms)
            with self.prefetch_lock:
                self.prefetched_seed = (tid, tname, ow, nether)
            self.last_available_counts = avail
            self.root.after(0, self.update_display_with_seed, tname, ow, nether)
            self.root.after(0, lambda: self.available_label.config(text=f"可用种子数：{avail}"))
            self.root.after(0, lambda: self.prefetch_label.config(
                text=f"预加载状态：就绪 ({tname})", fg="green"))
            self.log_queue.put(f"预加载成功：{tname} - {ow} (可用:{avail})")
            self.prefetch_fail_count = 0
        except Exception as e:
            self.prefetch_fail_count += 1
            self.root.after(0, lambda: self.prefetch_label.config(text="预加载状态：失败", fg="red"))
            self.log_queue.put(f"预加载失败：{str(e)}")
            self.log_queue.put(traceback.format_exc())
            if self.prefetch_fail_count >= 3:
                self.log_queue.put("预加载连续失败多次，请检查筛选条件或网络")
            else:
                # 延迟5秒后重试
                self.root.after(5000, self.trigger_prefetch)

    def update_display_with_seed(self, type_name, owseed, netherseed):
        self.info_text.set(
            f"类型：{type_name}\n主世界种子：{owseed}\n下界种子：{netherseed}"
        )

    # ---------- 百宝箱查询 ----------
    def query_match(self):
        match_id = self.match_id_entry.get().strip()
        if not match_id.isdigit():
            self.log_queue.put(f"查询失败：比赛ID必须为数字（输入：{match_id}）")
            self.match_result_text.set("")
            return

        api_base = self.api_base.get().rstrip('/')
        url = f"{api_base}/api/v2/seed/{match_id}"
        self.log_queue.put(f"正在请求种子值：{url}")

        owseed = None
        netherseed = None
        seed_success = False

        try:
            resp = requests.get(url, timeout=10)
            self.log_queue.put(f"种子值API状态码：{resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    seeds = data['data']['seeds']
                    owseed = seeds['overworldSeed']
                    netherseed = seeds['netherSeed']
                    seed_success = True
                else:
                    self.log_queue.put(f"种子值API返回success=false：{data.get('message', '未知错误')}")
            else:
                self.log_queue.put(f"种子值API返回HTTP {resp.status_code}，响应内容：{resp.text[:200]}")
        except Exception as e:
            self.log_queue.put(f"请求种子值异常：{str(e)}")

        url_info = f"{api_base}/api/v2/seedinfo/{match_id}"
        self.log_queue.put(f"正在请求详细信息：{url_info}")

        overworld_type = "未知"
        nether_type = "未知"
        variations = []
        info_success = False

        try:
            resp_info = requests.get(url_info, timeout=10)
            self.log_queue.put(f"详细信息API状态码：{resp_info.status_code}")
            if resp_info.status_code == 200:
                data_info = resp_info.json()
                if data_info.get('success'):
                    overworld_type = data_info['data'].get('overworld', '未知')
                    nether_type = data_info['data'].get('nether', '未知')
                    raw_variations = data_info['data'].get('variations', [])
                    if isinstance(raw_variations, str):
                        try:
                            variations = json.loads(raw_variations)
                        except:
                            variations = [raw_variations]
                    elif isinstance(raw_variations, list):
                        variations = raw_variations
                    else:
                        variations = []
                    info_success = True
                else:
                    self.log_queue.put(f"详细信息API返回success=false：{data_info.get('message', '未知错误')}")
            else:
                self.log_queue.put(f"详细信息API返回HTTP {resp_info.status_code}，响应内容：{resp_info.text[:200]}")
        except Exception as e:
            self.log_queue.put(f"请求详细信息异常：{str(e)}")

        self.match_result = {
            'overworld_type': overworld_type,
            'nether_type': nether_type,
            'variations': variations,
            'owseed': owseed,
            'netherseed': netherseed
        }

        if seed_success:
            seed_display = f"{owseed} / {netherseed}"
        else:
            seed_display = "获取失败（服务器错误）"

        if variations:
            if isinstance(variations, list):
                var_display = ', '.join(str(v) for v in variations)
            else:
                var_display = str(variations)
        else:
            var_display = "无"

        self.match_result_text.set(
            f"主世界类型: {overworld_type}\n"
            f"下界类型: {nether_type}\n"
            f"变种: {var_display}\n"
            f"种子: {seed_display}"
        )

        if info_success:
            self.log_queue.put(f"查询比赛ID {match_id} 成功（类型信息）")
        else:
            self.log_queue.put(f"查询比赛ID {match_id} 失败：无法获取任何信息")

    def import_match(self):
        if not hasattr(self, 'match_result'):
            messagebox.showinfo("提示", "请先查询一个比赛ID")
            return
        ow_type = self.match_result['overworld_type'].lower()
        type_map = {
            'buried_treasure': 1,
            'ruined_portal': 2,
            'desert_temple': 3,
            'village': 4,
            'shipwreck': 5
        }
        if ow_type in type_map:
            tid = type_map[ow_type]
            self.select_none_overworld()
            self.type_vars[tid].set(1)
        nether_type = self.match_result['nether_type'].lower()
        if nether_type in self.nether_vars:
            self.nether_vars[nether_type].set(1)
        variations = self.match_result.get('variations', [])
        if variations:
            if isinstance(variations, list):
                var_str = ','.join(str(v) for v in variations)
            else:
                var_str = str(variations)
            self.variation_text.set(var_str)
        self.on_overworld_change()
        self.on_nether_change()
        self.on_variation_change()
        messagebox.showinfo("导入成功", "已导入主世界/下界类型，变种已填入文本框")

    # ---------- 热键捕获 ----------
    def capture_hotkey(self, hotkey_type):
        self.hotkey_capturing = hotkey_type
        btn = self.btn_start_hotkey if hotkey_type == 'start' else self.btn_exit_hotkey
        btn.config(text="按下任意键...", relief=SUNKEN)
        from pynput import keyboard
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
            from pynput.keyboard import KeyCode
            return KeyCode.from_char(s.lower())
        else:
            from pynput.keyboard import Key
            try:
                return getattr(Key, s.lower())
            except AttributeError:
                return Key.f5

    # ---------- 配置保存与加载 ----------
    def save_config(self):
        config = {
            'api_base': self.api_base.get(),
            'selected_overworld': list(self.selected_overworld),
            'random_checked': self.random_var.get(),
            'selected_nether': list(self.selected_nether),
            'selected_variations': list(self.selected_variations),
            'variation_text': self.variation_text.get(),
            'completion_min': self.completion_min.get(),
            'completion_sec': self.completion_sec.get(),
            'use_elo': self.use_elo.get(),
            'elo_option': self.elo_option.get(),
            'custom_weights': {str(k): v.get() for k, v in self.custom_weights.items()},
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
            selected = config.get('selected_overworld', [])
            for tid in selected:
                if tid in self.type_vars:
                    self.type_vars[tid].set(1)
            if config.get('random_checked', 0):
                self.random_var.set(1)
            self.update_selected_overworld()
            nether = config.get('selected_nether', [])
            for key in nether:
                if key in self.nether_vars:
                    self.nether_vars[key].set(1)
            self.update_selected_nether()
            vars_list = config.get('selected_variations', [])
            for v in vars_list:
                if v in self.var_checkboxes:
                    self.var_checkboxes[v].set(1)
            self.variation_text.set(config.get('variation_text', ''))
            self.update_selected_variations()
            self.completion_min.set(config.get('completion_min', ''))
            self.completion_sec.set(config.get('completion_sec', ''))
            self.use_elo.set(config.get('use_elo', False))
            self.elo_option.set(config.get('elo_option', '1200+'))
            weights = config.get('custom_weights', {})
            for k, v in weights.items():
                if int(k) in self.custom_weights:
                    self.custom_weights[int(k)].set(v)
            self.update_elo_state()
            self.update_weight_total()
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

        from pynput import keyboard
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
                    # 实时获取逻辑，与预加载一致
                    if self.use_elo.get():
                        option = self.elo_option.get()
                        if option == "自定义":
                            possible_types = [tid for tid in range(1,6) if self.custom_weights[tid].get() > 0]
                            if possible_types:
                                weights = [self.custom_weights[tid].get() for tid in possible_types]
                                overworld_choice = random.choices(possible_types, weights=weights)[0]
                                selected_overworld = [overworld_choice]
                            else:
                                selected_overworld = list(range(1,6))
                        else:
                            possible_types = [tid for tid in range(1,6) if self.custom_weights[tid].get() > 0]
                            if possible_types:
                                weights = [self.custom_weights[tid].get() for tid in possible_types]
                                overworld_choice = random.choices(possible_types, weights=weights)[0]
                                selected_overworld = [overworld_choice]
                            else:
                                selected_overworld = list(range(1,6))
                    else:
                        selected_overworld = list(self.selected_overworld)

                    selected_nether = list(self.selected_nether)
                    self.update_selected_variations()
                    completion_ms = None
                    if self.completion_min.get() or self.completion_sec.get():
                        try:
                            minutes = int(self.completion_min.get() or 0)
                            seconds = int(self.completion_sec.get() or 0)
                            completion_ms = (minutes * 60 + seconds) * 1000
                        except:
                            pass
                    tid, tname, ow, nether, avail = fetch_seed(api_base, selected_overworld, selected_nether,
                                                               self.selected_variations, completion_ms)
                    seed_info = (tid, tname, ow, nether)
                    task(api_base, seed_info, self.log_queue, self.update_stats)
                except Exception as e:
                    self.log_queue.put(f"实时获取种子失败：{e}")
                    self.log_queue.put(traceback.format_exc())
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
