#!/usr/bin/env bash
set -euo pipefail

# SCFAI Course Selector - Setup (Linux/macOS)
# All deps via Tsinghua mirror for China accessibility

cd "$(dirname "$0")"

MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

echo ""
echo "============================================"
echo "   SCFAI Course Selector - Setup"
echo "============================================"
echo ""

# ---- 1. Check Python ----
echo "[1/6] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.8+ first."
    exit 1
fi
PYTHON="$(command -v python3)"
echo "      $($PYTHON --version) detected."

# ---- 2. Check Chrome ----
echo ""
echo "[2/6] Checking Chrome browser..."
if command -v google-chrome &>/dev/null || \
   command -v chromium-browser &>/dev/null || \
   command -v chromium &>/dev/null; then
    echo "      Chrome/Chromium found."
elif [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    echo "      Google Chrome found (macOS)."
else
    echo "      [WARN] Chrome not found!"
    echo "      Install from: https://www.google.com/chrome/"
    echo "      Or set google_path manually in main.py"
fi

# ---- 3. Create venv ----
echo ""
echo "[3/6] Setting up virtual environment..."
if [ -f "venv/bin/activate" ]; then
    echo "      venv already exists, skip."
else
    echo "      Creating virtual environment..."
    $PYTHON -m venv venv
    echo "      venv created."
fi

source venv/bin/activate

# ---- 4. Install dependencies ----
echo ""
echo "[4/6] Installing dependencies (Tsinghua mirror)..."
pip install --upgrade pip -q -i "$MIRROR"
pip install -r requirements.txt -q -i "$MIRROR"
echo "      Dependencies installed."

# ---- 5. Download ChromeDriver ----
echo ""
echo "[5/6] Preparing ChromeDriver..."
python updateDriver.py || echo "[WARN] ChromeDriver download failed. Retry: python updateDriver.py"

# ---- 6. Done ----
echo ""
echo "[6/6] Setup complete!"
echo ""
echo "============================================"
echo "   Run: bash run_app.sh"
echo "============================================"
echo ""

{
    echo "Press Enter to exit..."
    read -r
} 2>/dev/null || true
