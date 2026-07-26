import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"c:\Users\Administrator\Desktop\osint\bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

targets = ["def num_search", "def tg_search", "def ff_search", "def vnum_search", "def ifsc_search", "def help_command", "def start", "def status_command"]

for i, line in enumerate(lines, 1):
    for target in targets:
        if target in line.lower():
            print(f"Line {i}: {line.strip()}")
