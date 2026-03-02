import requests
import json
import time
from pynput import keyboard
from pynput.keyboard import Key, Controller

url = "http://43.143.231.104:8001/api/v2/seed?overworld=buried_treasure&completion=720000"

def fetch_seed():
    print("正在获取种子数据...")
    response = requests.get(url)
    data = json.loads(response.text)
    seed_data = data['data']
    return seed_data['overworldSeed'], seed_data['netherSeed']

def type_text(text):
    kb = Controller()
    for char in str(text):
        kb.tap(char)
        time.sleep(0.01)

owseed, netherseed = fetch_seed()
next_owseed, next_netherseed = fetch_seed()

print(f"Overworld Seed: {owseed}")
print(f"Nether Seed: {netherseed}")
print("游戏界面按F5开始练习，按F6退出程序")

kb = Controller()

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
    next_owseed, next_netherseed = fetch_seed()
    print(f"Overworld Seed: {owseed}")
    print(f"Nether Seed: {netherseed}")

def on_press(key):
    if key == Key.f5:
        task()
    if key == Key.f6:
        return False

with keyboard.Listener(on_press=on_press) as lst:
    lst.join()