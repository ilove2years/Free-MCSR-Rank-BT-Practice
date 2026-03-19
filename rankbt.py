import requests
import json
import time
from pynput import keyboard
from pynput.keyboard import Key, Controller

# 开局类型映射（仅保留核心映射，无冗余注释）
overworld_types = {
    1: "buried_treasure",
    2: "ruined_portal",
    3: "desert_temple",
    4: "village",
    5: "shipwreck",
    6: "random"
}

# 选择开局类型（极简输入逻辑，无校验）
def select_overworld_type():
    print("请选择开局类型:\n1.宝藏\n2.废门\n3.沙漠神殿\n4.村庄\n5.沉船\n6.随机开局（bushi）")
    choice = int(input("请输入数字后回车(1~6):"))
    return choice

# 获取动态URL（随机开局每次选不同类型）
def get_url(choice):
    if choice == 6:
        import random
        types = [v for k, v in overworld_types.items() if k != 6]
        return f"http://43.143.231.104:8001/api/v2/seed?overworld={random.choice(types)}&completion=720000"
    return f"http://43.143.231.104:8001/api/v2/seed?overworld={overworld_types[choice]}&completion=720000"

# 获取种子（极简逻辑，无异常处理）
def fetch_seed(choice):
    print("正在获取种子数据...")
    response = requests.get(get_url(choice))
    data = json.loads(response.text)
    seed_data = data['data']
    return seed_data['overworldSeed'], seed_data['netherSeed']

# 输入文本（与参考代码完全一致）
def type_text(text):
    kb = Controller()
    for char in str(text):
        kb.tap(char)
        time.sleep(0.01)

# 选择开局类型
choice = select_overworld_type()

# 初始化种子
owseed, netherseed = fetch_seed(choice)
next_owseed, next_netherseed = fetch_seed(choice)

# 基础提示（与参考代码一致）
print(f"Overworld Seed: {owseed}")
print(f"Nether Seed: {netherseed}")
print("游戏主界面按F5开始练习，按F6退出程序")

kb = Controller()

# 核心任务逻辑（与参考代码完全一致，无修改）
def task():
    global owseed, netherseed, next_owseed, next_netherseed
    
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
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.enter)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)

    type_text(owseed)
    kb.tap(Key.tab)
    time.sleep(0.1)

    type_text(netherseed)
    kb.tap(Key.tab)

    type_text(owseed)

    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.tab)
    kb.tap(Key.enter)

    owseed, netherseed = next_owseed, next_netherseed
    next_owseed, next_netherseed = fetch_seed(choice)
    print(f"Overworld Seed: {owseed}")
    print(f"Nether Seed: {netherseed}")

# 按键监听（与参考代码完全一致）
def on_press(key):
    if key == Key.f5:
        task()
    if key == Key.f6:
        return False

with keyboard.Listener(on_press=on_press) as lst:
    lst.join()
