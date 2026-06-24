#!/usr/bin/env bash
set -euo pipefail

# SCFAI 选课助手 - 启动脚本 (Linux/macOS)

cd "$(dirname "$0")"

# 检查虚拟环境，不存在则自动执行配置
if [ ! -f "venv/bin/activate" ]; then
    echo "未检测到虚拟环境，正在自动执行环境配置..."
    echo ""
    bash setup.sh
    if [ ! -f "venv/bin/activate" ]; then
        echo "[错误] 环境配置失败，请检查后重试。"
        exit 1
    fi
fi

# 激活虚拟环境
source venv/bin/activate
echo "已激活虚拟环境"

# 检查 main.py
if [ ! -f "main.py" ]; then
    echo "[错误] 找不到 main.py 文件"
    exit 1
fi

# 运行
python main.py

{
    echo ""
    echo "按任意键退出..."
    read -r
} 2>/dev/null || true
