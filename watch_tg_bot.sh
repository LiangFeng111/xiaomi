#!/bin/bash
# 进入tg_bot.py所在目录（请根据实际情况修改路径）
cd "$(dirname "$0")"

# 检查tg_bot.py是否在运行，如果没有则启动
pgrep -f "python3 tg_bot.py" > /dev/null || nohup python3 tg_bot.py > tg_bot.log 2>&1 & 