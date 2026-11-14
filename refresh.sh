#!/data/data/com.termux/files/usr/bin/sh
# 在手机上一条命令重新体检并生成配置（dsh 环境里也可以直接跑）
cd "$(dirname "$0")" || exit 1
python3 build.py
echo
echo "生成完毕："
ls -l tvbox-multi.json tvbox-single.json tvbox-lite.json
