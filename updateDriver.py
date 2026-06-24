"""
ChromeDriver 自动下载/更新工具。
- 自动检测当前操作系统和架构
- 优先使用国内 npmmirror 镜像（国内可访问）
- 下载的驱动存放在 driver/ 目录
"""
import os
import sys
import stat
import shutil
import zipfile
import json
import subprocess
import tempfile

try:
    import requests
except ImportError:
    print("没有找到 requests，尝试下载...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install', 'requests',
        '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'
    ])
    import requests

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))
DRIVER_DIR = os.path.join(ROOT, "driver")

# API 地址（只有 Google 提供 JSON API，npmmirror 只镜像了二进制文件）
API_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)

# 下载镜像：国内优先 npmmirror，回退 Google Storage
DOWNLOAD_MIRRORS = [
    "https://registry.npmmirror.com/-/binary/chrome-for-testing/",
    "https://storage.googleapis.com/chrome-for-testing-public/",
]

REQUEST_TIMEOUT = 30  # 秒


def detect_platform():
    """检测当前平台，返回 (platform_key, driver_filename)。"""
    system = sys.platform
    if system == "win32":
        return "win64", "chromedriver.exe"
    elif system == "darwin":
        import platform as pf
        machine = pf.machine()
        if machine == "arm64":
            return "mac-arm64", "chromedriver"
        else:
            return "mac-x64", "chromedriver"
    else:
        return "linux64", "chromedriver"


def get_chrome_version(chrome_path):
    """获取 Chrome 版本号，返回如 '149.0.7827.197'。

    依次尝试：User Data/Last Version 文件 → PowerShell → --version 参数。
    """
    # 方法1: 读 Chrome 用户目录下的 Last Version 文件（最可靠，无需启动 Chrome）
    for user_data_base in [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application"),
    ]:
        last_ver_file = os.path.join(user_data_base, "Last Version")
        if os.path.isfile(last_ver_file):
            try:
                with open(last_ver_file, "r") as f:
                    return f.read().strip()
            except Exception:
                pass

    # 方法2: 通过文件属性读取（Windows PowerShell）
    if sys.platform == "win32":
        try:
            ps_cmd = f'(Get-Item "{chrome_path}").VersionInfo.FileVersion'
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip()
            if version:
                print(f"  PowerShell 检测到版本: {version}")
                return version
        except Exception:
            pass

    # 方法3: --version 参数（Linux/Mac 首选，Windows 可能超时）
    try:
        result = subprocess.run(
            [chrome_path, "--version"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout.strip() or result.stderr.strip()
        for token in output.split():
            parts = token.split(".")
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
                return token
    except Exception:
        pass

    return None


def find_chrome_binary():
    """查找 Chrome 可执行文件路径。"""
    if sys.platform == "win32":
        candidates = [shutil.which("chrome")]
        for env_var, subpath in [
            ("ProgramFiles", "Google\\Chrome\\Application\\chrome.exe"),
            ("ProgramFiles(x86)", "Google\\Chrome\\Application\\chrome.exe"),
            ("LOCALAPPDATA", "Google\\Chrome\\Application\\chrome.exe"),
        ]:
            base = os.environ.get(env_var, "")
            if base:
                candidates.append(os.path.join(base, subpath))
    elif sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidates = [
            shutil.which("google-chrome"),
            shutil.which("chromium-browser"),
            shutil.which("chromium"),
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
        ]

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def get_chrome_download_url(version, platform_key):
    """构建给定版本的 ChromeDriver 下载路径部分。
    返回 (path_part, display_version)，例如 ('149.0.7827.197/win64/chromedriver-win64.zip', '149.0.7827.197')。
    """
    return (
        f"{version}/{platform_key}/chromedriver-{platform_key}.zip",
        version,
    )


def fetch_json(url):
    """从 URL 获取 JSON 数据。"""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def find_latest_download_url(data, platform_key):
    """从 API 返回数据中找到最新 Stable ChromeDriver 下载链接和版本号。"""
    channels = data.get("channels", {})
    stable = channels.get("Stable", {})
    version = stable.get("version", "unknown")
    downloads = stable.get("downloads", {}).get("chromedriver", [])

    for item in downloads:
        if item.get("platform") == platform_key:
            return item["url"], version

    raise RuntimeError(f"未找到平台 '{platform_key}' 的 ChromeDriver 下载链接。")


def download_file(url, dest_path):
    """下载文件到指定路径。"""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT * 5)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)


def extract_chromedriver(zip_path, extract_dir, driver_filename):
    """解压并找到 chromedriver 可执行文件。"""
    with zipfile.ZipFile(zip_path) as zf:
        # 查找以 chromedriver 结尾的文件（含子目录路径）
        driver_members = [
            n for n in zf.namelist()
            if n.endswith("chromedriver") or n.endswith("chromedriver.exe")
        ]
        if not driver_members:
            raise RuntimeError("压缩包中未找到 chromedriver 文件。")

        # 选择最短路径（通常在根目录或一层子目录下）
        driver_archive_path = min(driver_members, key=len)
        zf.extract(driver_archive_path, extract_dir)

    extracted_path = os.path.join(extract_dir, driver_archive_path)
    return extracted_path


def update_driver(chrome_path=None):
    """下载/更新 ChromeDriver，匹配本地 Chrome 版本。

    流程：
    1. 检测本地 Chrome 版本
    2. 尝试下载精确匹配版本的 ChromeDriver
    3. 精确版本不存在时回退到主版本号
    4. 都不行则下载最新 Stable 版本
    """
    platform_key, driver_filename = detect_platform()
    print(f"检测到平台: {platform_key}")

    os.makedirs(DRIVER_DIR, exist_ok=True)

    # 检测本地 Chrome 版本
    local_version = None
    if chrome_path is None:
        chrome_path = find_chrome_binary()
    if chrome_path:
        print(f"检测 Chrome: {chrome_path}")
        local_version = get_chrome_version(chrome_path)
        if local_version:
            print(f"Chrome 版本: {local_version}")

    # 构建候选版本列表：精确 → 递次缩短 → 兜底最新
    candidate_versions = []
    if local_version:
        parts = local_version.split(".")
        # 149.0.7827.197 → 149.0.7827 → 149.0  → 149
        for i in range(len(parts), 0, -1):
            v = ".".join(parts[:i])
            if v not in candidate_versions:
                candidate_versions.append(v)

    # 尝试候选版本
    for version in candidate_versions:
        path_part, _ = get_chrome_download_url(version, platform_key)
        if try_download_mirrors(path_part, driver_filename):
            return

    # 候选版本都不存在，回退到 API 获取最新 Stable
    if local_version:
        print(f"未找到 Chrome {local_version} 的 ChromeDriver，尝试最新 Stable...")
    try:
        data = fetch_json(API_URL)
        original_url, latest_version = find_latest_download_url(data, platform_key)
        path_part = original_url.replace(
            "https://storage.googleapis.com/chrome-for-testing-public/", ""
        )
        if local_version:
            print(f"注意: Chrome 版本 ({local_version}) 与 ChromeDriver ({latest_version}) 不匹配")
            print(f"      建议更新 Chrome 浏览器或手动指定版本。")
        if try_download_mirrors(path_part, driver_filename):
            return
    except Exception as e:
        raise RuntimeError(f"获取最新 ChromeDriver 信息失败: {e}")

    raise RuntimeError("所有下载尝试均失败，请检查网络连接。")


def try_download_mirrors(path_part, driver_filename):
    """尝试从各镜像下载指定 path_part 的 ChromeDriver。成功返回 True，失败返回 False。"""
    target_path = os.path.join(DRIVER_DIR, driver_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "chromedriver.zip")

        for base in DOWNLOAD_MIRRORS:
            url = base + path_part
            try:
                print(f"  尝试: {url[:90]}...")
                download_file(url, zip_path)
                print("  下载完成，正在解压...")
                extracted_path = extract_chromedriver(zip_path, tmpdir, driver_filename)

                if os.path.exists(target_path):
                    os.remove(target_path)
                shutil.move(extracted_path, target_path)

                if sys.platform != "win32":
                    os.chmod(target_path, os.stat(target_path).st_mode | stat.S_IEXEC)

                print(f"ChromeDriver → {target_path}")
                return True
            except Exception as e:
                print(f"  失败: {e}")
                continue

    return False


if __name__ == '__main__':
    try:
        update_driver()
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)
