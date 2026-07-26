import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"c:\Users\Administrator\Desktop\osint\bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if "search" in line.lower() and ("total" in line.lower() or "count" in line.lower() or "today" in line.lower() or "save" in line.lower() or "data[" in line.lower()):
        print(f"Line {i}: {line.strip()}")
