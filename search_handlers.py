import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"c:\Users\Administrator\Desktop\osint\bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if "is_private_approved" in line.lower() or "private usage" in line.lower():
        print(f"Line {i}: {line.strip()}")
