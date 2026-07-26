import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"c:\Users\Administrator\Desktop\osint\bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if "def stats" in line.lower() or "stats_command" in line.lower() or "stats" in line.lower():
        if "is_fully_verified" not in line.lower():
            print(f"Line {i}: {line.strip()}")
