import sys
import json
import os
import time
import shutil
import subprocess
from queue import Queue
from datetime import datetime
from threading import Thread, Event
try:
    from selenium import webdriver
except ImportError:
    print("未找到 selenium 库，正在尝试安装...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'selenium',
                           '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'])
    from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException


# ============================================================
# 配置文件加载
# ============================================================

def load_config():
    """从 config.json 读取配置，缺失时自动创建默认文件。"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(config_path):
        _create_default_config(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 解析时间
    begin_time = datetime.strptime(cfg.get("begin_time", "2025-9-25 13:00:30"), "%Y-%m-%d %H:%M:%S")
    delay = float(cfg.get("delay_time", 0.8))
    click_burst = int(cfg.get("click_burst", 5))
    chrome_path = cfg.get("chrome_path", "").strip()
    fuzzy_match = bool(cfg.get("fuzzy_match", False))
    dual_mode = bool(cfg.get("dual_mode", True))
    courses = cfg.get("courses", {})

    # 清理 courses 中的 _comment 等非课程条目（键以 _ 开头的跳过）
    courses = {k: v for k, v in courses.items() if not k.startswith("_")}

    # 标准化 course 值：字符串 → {label/class_id} 对象
    normalized = {}
    for k, v in courses.items():
        if isinstance(v, str):
            v = v.strip()
            normalized[k] = {"label": v, "class_id": ""}
        elif isinstance(v, dict):
            normalized[k] = {
                "label": (v.get("label", "") or "").strip(),
                "class_id": (v.get("class_id", "") or "").strip(),
            }
        else:
            normalized[k] = {"label": "", "class_id": ""}
    courses = normalized

    return {
        "begin_time": begin_time,
        "delay_time": delay,
        "click_burst": click_burst,
        "chrome_path": chrome_path or None,
        "fuzzy_match": fuzzy_match,
        "dual_mode": dual_mode,
        "courses": courses,
    }


def _create_default_config(path):
    """生成一份默认配置文件。"""
    default = {
        "begin_time": "2025-9-25 13:00:30",
        "delay_time": 0.8,
        "click_burst": 8,
        "chrome_path": "",
        "fuzzy_match": True,
        "dual_mode": True,
        "courses": {
            "体育2": {
                "label": "羽毛球",
                "class_id": ""
            }
        }
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(default, f, ensure_ascii=False, indent=4)
    print(f"已创建默认配置文件: {path}")

# ============================================================
# 跨平台路径检测
# ============================================================

def _find_chrome_binary():
    """检测 Chrome 浏览器可执行文件路径。"""
    if sys.platform == "win32":
        candidates = []

        # 方法1: 注册表（最可靠）
        try:
            import winreg
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for subkey in (
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                ):
                    try:
                        with winreg.OpenKey(root, subkey) as key:
                            path, _ = winreg.QueryValueEx(key, "")
                            if path and os.path.exists(path):
                                candidates.append(path)
                    except OSError:
                        pass
        except Exception:
            pass

        # 方法2: PATH 中查找
        chrome = shutil.which("chrome")
        if chrome:
            candidates.append(chrome)

        # 方法3: 常见安装路径
        local = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates += [
            os.path.join(prog_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(prog_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        ]

    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    else:  # Linux
        candidates = []
        chrome = shutil.which("google-chrome") or shutil.which("chromium-browser") or shutil.which("chromium")
        if chrome:
            candidates.append(chrome)
        candidates += [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium",
        ]

    # 去重 + 检测
    seen = set()
    for path in candidates:
        path = os.path.normpath(path)
        if path in seen:
            continue
        seen.add(path)
        if os.path.exists(path):
            print(f"找到 Chrome: {path}")
            return path

    print("警告: 未找到 Chrome 浏览器。")
    print("   - 如已安装，请在 main.py 的 Properties 类中手动设置 google_path")
    print("   - 如未安装，请从 https://www.google.com/chrome/ 下载安装")
    return None


def _get_chromedriver_path():
    """获取 ChromeDriver 路径（存放在 driver/ 目录下）。"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    driver_dir = os.path.join(project_root, "driver")
    if sys.platform == "win32":
        return os.path.join(driver_dir, "chromedriver.exe")
    else:
        return os.path.join(driver_dir, "chromedriver")


class Properties:
    REMOTE_DEBUG_PORT = 9222
    _login_done = Event()  # 跨线程登录信号

    @classmethod
    def init_from_config(cls, cfg):
        """用配置文件初始化类属性。"""
        cls.begin = cfg["begin_time"]
        cls.DELAY_TIME = cfg["delay_time"]
        cls.CLICK_BURST = cfg["click_burst"]
        cls.FUZZY_MATCH = cfg["fuzzy_match"]
        cls.courseList = cfg["courses"]
        cls.dual_mode = bool(cfg.get("dual_mode", True))
        cls.google_path = None
        if cfg["chrome_path"] and os.path.exists(cfg["chrome_path"]):
            cls.google_path = cfg["chrome_path"]
        else:
            cls.google_path = _find_chrome_binary()
        cls.chromedriver_path = _get_chromedriver_path()
        # 重置登录信号（避免重复运行时 Event 残留）
        cls._login_done.clear()

    def _create_driver(self, attach_to_existing=False):
        """创建单个 Chrome WebDriver 实例。

        attach_to_existing=True: 连接到已有 Chrome 实例（第二个 tab）
        """
        if not self.google_path:
            raise RuntimeError(
                "未找到 Chrome 浏览器，无法启动。\n"
                "  1. 确认已安装 Chrome: https://www.google.com/chrome/\n"
                "  2. 或在 config.json 中设置 chrome_path 为你的 Chrome 可执行文件路径"
            )
        from selenium.webdriver.chrome.service import Service
        service = Service(self.chromedriver_path)
        options = Options()
        options.binary_location = self.google_path

        if attach_to_existing:
            # 连接到已有 Chrome 实例（共享 session，多 tab）
            options.add_experimental_option("debuggerAddress",
                                            f"127.0.0.1:{self.REMOTE_DEBUG_PORT}")
        else:
            # 首次启动：开启远程调试端口
            options.add_argument(f"--remote-debugging-port={self.REMOTE_DEBUG_PORT}")

        try:
            return webdriver.Chrome(options=options, service=service)
        except Exception as e:
            if attach_to_existing:
                raise  # 连接失败不重试，可能主实例还没启动
            print(f"初始化 WebDriver 时出错: {e}")
            print("驱动异常，正在尝试下载或更新...")
            try:
                from updateDriver import update_driver
                update_driver(self.google_path)
                print("驱动下载/更新完成。")
                service = Service(self.chromedriver_path)
                return webdriver.Chrome(options=options, service=service)
            except Exception as update_e:
                print(f"驱动下载/更新失败: {update_e}")
                raise

    def __init__(self, count=1):
        self.drivers = []
        # 第一个 driver：启动 Chrome 并开启调试端口
        driver1 = self._create_driver(attach_to_existing=False)
        self.drivers.append(driver1)
        print("浏览器窗口 1/主实例 已启动。")

        # 后续 driver：连接到同一个 Chrome 实例（多 tab）
        for i in range(1, count):
            try:
                driver_n = self._create_driver(attach_to_existing=True)
                # 在新 tab 打开
                driver_n.switch_to.new_window('tab')
                self.drivers.append(driver_n)
                print(f"浏览器 Tab {i+1} 已附加到主实例。")
            except Exception as e:
                print(f"附加 Tab {i+1} 失败: {e}")

    @property
    def driver(self):
        """向后兼容：返回第一个 driver。"""
        return self.drivers[0] if self.drivers else None


class GetCourse:
    # ── URL 常量 ──
    login_url = "http://ids.scfai.edu.cn/#/login"
    dashboard_url = "http://ids.scfai.edu.cn/#/dashboard"
    course_selection_url = "https://jwjx.scfai.edu.cn/enroll/Home"      # 备用
    list_url = "https://jwjx.scfai.edu.cn/enroll/CourseStuSelectionList"  # 轮询页

    # ── 节奏常量 ──
    LOGIN_POLL_INTERVAL = 2       # 等待登录时轮询间隔
    COUNTDOWN_LONG = 5            # 距开始 >10s 时的等待间隔
    COUNTDOWN_SHORT = 0.1         # 距开始 ≤10s 时的等待间隔
    BURST_GAP = 0.3               # 轮询模式连击间隔
    AGGRESSIVE_GAP = 0.2          # 激进模式重试间隔（过短可能触发限流）
    AGGRESSIVE_REFRESH_GAP = 0.3  # 激进模式刷新后等待
    AGGRESSIVE_MAX_RETRIES = 300  # 单个课程最大连续重试次数（防死循环）
    MODAL_RENDER_GAP = 0.3        # Modal 表格渲染等待

    def __init__(self, courseList, driver=None, fuzzy_match=False):
        self.driver = driver
        self.courseList = courseList
        self.fuzzy_match = fuzzy_match
        self.web_wait = WebDriverWait(self.driver, 4)

    def _course_title_xpath(self, name):
        """根据模糊/精确模式生成课程标题 XPath。引号自动转义。"""
        # 移除引号防注入（课程名实际不会含引号）
        safe = name.replace('"', '').replace("'", '')
        if self.fuzzy_match:
            return f'//a[contains(@title, "{safe}")]'
        else:
            return f'//a[@title="{safe}"]'

    def wait(self, retries=1, *element):
        """ 显式等待 - 单元素 """
        while retries > 0:
            try:
                wait = self.web_wait.until(EC.presence_of_element_located(element))
                return wait
            except TimeoutException:
                retries -= 1
                try:
                    ele = self.driver.find_element(*element)
                    self.driver.execute_script("arguments[0].scrollIntoView();", ele)
                except Exception as e:
                    print(f"元素未找到，正在重试... 错误: {e}")
                print("正在重试单元素等待...")
        raise NoSuchElementException("重试后仍未找到元素")



    def close(self):
        """ 关闭可能的弹窗 """
        try:
            close_button = self.driver.find_element(By.XPATH, "//i[@aria-label=\"图标: close\"]")
            close_button.click()
            print("已关闭一个弹窗。")
        except Exception:
            pass

    def select(self, name):
        """ 执行选课操作 — 在二级 Modal 中智能选择教学班。

        两层独立匹配：
        1. 课程名（name）→ 主列表定位课程（受 fuzzy_match 控制）
        2. label/class_id → Modal 内筛选教学班（各自模糊匹配，OR 关系）

        回退逻辑：
        - 时间冲突（exclamation-circle）→ 跳过
        - 容量已满 / 已选 / 教学班已锁定 → 跳过
        - label/class_id 都为空 → 自动选第一个可用班
        - 匹配失败 → 回退到下一个教学班
        """
        # 1. 点击课程链接打开 Modal
        course_link = self.wait(2, By.XPATH, self._course_title_xpath(name))
        course_link.click()
        print(f"已点击课程: {name}")

        # 等待 Modal 渲染
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class,'select-class-info-modal')]")
                )
            )
            time.sleep(self.MODAL_RENDER_GAP)  # 给 Modal 内部表格一点渲染时间
        except TimeoutException:
            print(f"  Modal 未弹出，可能是课程已选或页面未响应。")
            self.close()
            return False

        target = self.courseList.get(name, {"label": "", "class_id": ""})
        if isinstance(target, str):
            target = {"label": target, "class_id": ""}
        target_label = (target.get("label", "") or "").strip()
        target_cid  = (target.get("class_id", "") or "").strip()

        # 2. 等待 Modal 中的教学班表格出现
        row_xpath = (
            "//div[contains(@class,'select-class-info-modal')]"
            "//tbody[@class='ant-table-tbody']/tr"
        )
        rows = self.driver.find_elements(By.XPATH, row_xpath)
        if not rows:
            print(f"  未找到教学班列表，可能是页面加载问题。")
            self.close()
            return False

        print(f"  找到 {len(rows)} 个教学班，label='{target_label}' class_id='{target_cid}'")

        # 3. 遍历教学班行，找第一个可选的
        for idx, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 9:
                continue

            # --- 状态检测（最后列 td[9]） ---
            status_text = cells[8].text.strip()

            if status_text in ("已选", "容量已满", "教学班已锁定"):
                print(f"    班 {idx+1}: 跳过（{status_text}）")
                continue

            # 必须有 checkbox 才可选
            checkboxes = cells[8].find_elements(By.XPATH, ".//input[@type='checkbox']")
            if not checkboxes:
                print(f"    班 {idx+1}: 跳过（无选择框，状态: {status_text or '无'}）")
                continue

            # --- 冲突检测（td[1] 内的图标） ---
            # 时间冲突
            conflicts = cells[0].find_elements(By.XPATH, ".//*[contains(@aria-label,'exclamation-circle')]")
            if conflicts:
                print(f"    班 {idx+1}: 跳过（时间冲突）")
                continue

            # 教学班已锁定
            locks = cells[0].find_elements(By.XPATH, ".//*[contains(@aria-label,'lock')]")
            if locks:
                print(f"    班 {idx+1}: 跳过（教学班已锁定）")
                continue

            # --- 匹配逻辑 ---
            class_id_text = cells[0].text.strip()   # 教学班号
            label_text = cells[5].text.strip() if len(cells) > 5 else ""  # 标签
            capacity_text = cells[4].text.strip() if len(cells) > 4 else ""  # 容量

            matched = False
            reason_parts = []

            if not target_label and not target_cid:
                # 都没指定 → 第一个可用班
                matched = True
                reason_parts.append("自动（第一个可用）")
            else:
                # label 和 class_id 独立模糊匹配（包含即可），OR 关系
                if target_label and target_label in label_text:
                    matched = True
                    reason_parts.append(f"标签含'{target_label}'")
                if target_cid and target_cid in class_id_text:
                    matched = True
                    reason_parts.append(f"班号含'{target_cid}'")

            reason = " + ".join(reason_parts) if reason_parts else ""

            if not matched:
                print(f"    班 {idx+1}: 跳过（不匹配）"
                      f" 班号={class_id_text} 标签={label_text}")
                continue

            # --- 执行选择 ---
            print(f"    班 {idx+1}: ✓ {reason} → 班号={class_id_text} 容量={capacity_text} 标签={label_text}")
            try:
                checkboxes[0].click()

                # 初步确认
                confirm_1 = self.driver.find_element(By.XPATH,
                    "//div[@class='select-class-info-modal']"
                    "//button[.//span[contains(text(),'选')]]")
                confirm_1.click()
                print("    已点击初步选课确认。")

                # 最终确认
                confirm_2 = self.driver.find_element(By.XPATH,
                    "//div[@class='ant-modal-confirm-btns']"
                    "//button[.//span[contains(text(),'确')]]")
                confirm_2.click()
                print("    已点击最终确认。")

                self.close()
                return True

            except Exception as e:
                print(f"    班 {idx+1}: 点击失败 → {e}")
                continue

        # 所有行遍历完都没匹配
        print(f"  课程 {name}: 无可用教学班（label='{target_label}' class_id='{target_cid}'）。")
        self.close()
        return False

    def isSelected(self, name):
        """ 判断是否成功选到目标课程。在已选课程侧边栏中查找课程名。 """
        safe = name.replace('"', '').replace("'", '')
        try:
            # 在已选课程侧边栏（Ant Design tabs）中查找含课程名的 tab
            tabs = self.driver.find_elements(
                By.XPATH,
                f"//*[contains(@class,'ant-tabs-tab') and contains(.,'{safe}')]"
            )
            if tabs:
                print(f"课程 {name} 已在已选列表中。")
                return True
        except Exception as e:
            print(f"检查已选课程时出错: {e}")
            return False

        # 模糊匹配：检查 name 是否为某个 tab 文本的子串
        if self.fuzzy_match:
            try:
                all_tabs = self.driver.find_elements(By.XPATH,
                    "//*[contains(@class,'ant-tabs-tab')]")
                for tab in all_tabs:
                    if name in tab.text:
                        print(f"课程 {name} 模糊匹配 {tab.text.strip()[:20]}... 已成功选择！")
                        return True
            except Exception:
                pass
        return False

    def circle(self, courseQueue):
        """ 循环尝试选课 — 直接轮询 CourseStuSelectionList 页面。

        前端容易崩溃，策略是「多击少刷」：
        - 同一个课程连点 N 次，中间不刷新
        - 连点全部失败才刷新页面
        """
        list_url = self.list_url
        CLICK_BURST = Properties.CLICK_BURST   # 从配置读取

        while True:
            # 直接进入选课列表页（不走 UI 点击链路）
            if self.driver.current_url != list_url:
                print(f"导航至选课列表: {list_url}")
                self.driver.get(list_url)
            time.sleep(Properties.DELAY_TIME)

            temp_courses_to_check = []
            while not courseQueue.empty():
                courseName = courseQueue.get()
                print(f"正在尝试选择: {courseName}")

                select_result = False
                for attempt in range(1, CLICK_BURST + 1):
                    try:
                        if self.select(courseName):
                            select_result = True
                            break
                    except Exception as e:
                        print(f"  {courseName} 第 {attempt}/{CLICK_BURST} 次点击异常: {e}")
                    time.sleep(self.BURST_GAP)

                temp_courses_to_check.append((courseName, select_result))

            for course_name, was_selected in temp_courses_to_check:
                if was_selected and self.isSelected(course_name):
                    print(f"课程 {course_name} 已确认选上。")
                elif was_selected and not self.isSelected(course_name):
                    print(f"课程 {course_name} 选择操作成功但未在已选列表中确认，重新加入队列。")
                    courseQueue.put(course_name)
                elif not was_selected:
                    print(f"课程 {course_name} 本次未选择成功 (可能不可选)，重新加入队列以便后续重试。")
                    courseQueue.put(course_name)

            if courseQueue.empty():
                print("所有课程均已处理并确认（或已无余课）。")
                return True

            print(f"本轮结束，{len(temp_courses_to_check)} 门课程中仍有 {courseQueue.qsize()} 门待选。")
            print("刷新页面后继续下一轮...")
            self.driver.refresh()
            time.sleep(Properties.DELAY_TIME)

    def _login_and_wait(self, label="", is_primary=True):
        """登录 + 等待时间 → 直达 CourseStuSelectionList。

        is_primary=True:  主线程负责登录，完成后通知其他线程。
        is_primary=False: 等待主线程登录完成后，直接跳转。
        """
        list_url = self.list_url

        if is_primary:
            # ── 主线程：执行完整登录 ──
            self.driver.maximize_window()
            print(f"[{label}] 1. 导航至登录页面: {self.login_url}")
            print(f"[{label}]    请在浏览器中手动登录（只需一次）。")
            self.driver.get(self.login_url)

            print(f"[{label}] 2. 等待登录成功: {self.dashboard_url}")
            while True:
                current_url = self.driver.current_url
                if current_url.startswith(self.dashboard_url):
                    print(f"[{label}]    登录成功！")
                    break
                time.sleep(self.LOGIN_POLL_INTERVAL)

            # 通知其他线程：登录完成
            Properties._login_done.set()
            print(f"[{label}]    已通知其他 Tab 登录完成。")

        else:
            # ── 副线程：等待主线程登录完成 ──
            print(f"[{label}] 等待主 Tab 登录...")
            Properties._login_done.wait()  # 阻塞直到主线程 set()
            print(f"[{label}] 主 Tab 已登录，直接进入选课列表。")

        # ── 直达 CourseStuSelectionList ──
        print(f"[{label}] 3. 直达选课列表: {list_url}")
        self.driver.get(list_url)
        time.sleep(Properties.DELAY_TIME)

        # 等待表格加载
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//table//tbody//tr"))
            )
        except TimeoutException:
            print(f"[{label}]    警告: 页面表格未加载，继续尝试...")

        # 等待开始时间（两个线程都要等）
        print(f"[{label}] 4. 等待选课时间 {Properties.begin}...")
        while datetime.now() <= Properties.begin:
            remaining = (Properties.begin - datetime.now()).total_seconds()
            if remaining > 10:
                print(f"[{label}]    距开始还有 {remaining:.0f} 秒")
                time.sleep(self.COUNTDOWN_LONG)
            else:
                time.sleep(self.COUNTDOWN_SHORT)
        print(f"[{label}]    时间到！")

    def run_poll(self, courseQueue):
        """ [轮询模式] 逐门尝试，刷新轮换 """
        self._login_and_wait("轮询", is_primary=True)
        print("[轮询] 5. 开始轮询选课...")
        result = self.circle(courseQueue)
        if result:
            print("[轮询] 所有课程均已处理。")
        else:
            print("[轮询] 选课循环结束，可能有课程未选上。")

    def run_aggressive(self, courseQueue):
        """ [激进模式] 连续重试：元素存在就不刷新，极速连点 """
        self._login_and_wait("激进", is_primary=False)

        list_url = self.list_url
        print("[激进] 5. 开始激进重试...")

        while not courseQueue.empty():
            courseName = courseQueue.get()
            print(f"[激进] ★ 聚焦: {courseName}")

            self.driver.get(list_url)
            time.sleep(Properties.DELAY_TIME)

            fail_count = 0
            while True:
                try:
                    # 等元素可见再操作
                    link = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located(
                            (By.XPATH, self._course_title_xpath(courseName))
                        )
                    )
                    if self.select(courseName):
                        # select() 已走完 checkbox→确认→确认 全流程，服务器已登记
                        # isSelected() 可能因页面缓存未刷新而短暂返回 False，信任 select()
                        if self.isSelected(courseName):
                            print(f"[激进] ✓ {courseName} 已确认选上！")
                        else:
                            print(f"[激进] ✓ {courseName} 已提交（页面暂未刷新，信任服务端）")
                        break

                    fail_count += 1
                    if fail_count >= self.AGGRESSIVE_MAX_RETRIES:
                        print(f"[激进]   {courseName} 已达 {self.AGGRESSIVE_MAX_RETRIES} 次上限，刷新...")
                        self.driver.refresh()
                        time.sleep(self.AGGRESSIVE_REFRESH_GAP)
                        fail_count = 0
                    elif fail_count % 50 == 0:
                        print(f"[激进]   {courseName} 已重试 {fail_count} 次...")
                    time.sleep(self.AGGRESSIVE_GAP)

                except TimeoutException:
                    # 元素消失 → 刷新
                    print(f"[激进]   元素消失，刷新...")
                    self.driver.refresh()
                    time.sleep(self.AGGRESSIVE_REFRESH_GAP)
                    fail_count = 0

                except Exception as e:
                    fail_count += 1
                    if fail_count >= self.AGGRESSIVE_MAX_RETRIES:
                        print(f"[激进]   异常超限，刷新...")
                        self.driver.refresh()
                        time.sleep(self.AGGRESSIVE_REFRESH_GAP)
                        fail_count = 0
                    elif fail_count % 30 == 0:
                        print(f"[激进]   异常({fail_count}次): {e}")
                    time.sleep(self.AGGRESSIVE_GAP)

        print("[激进] 所有课程已处理。")


def run(courseList, drivers, dual_mode=True):
    """ 启动选课。

    drivers: WebDriver 实例列表
    dual_mode: True=双窗口（轮询+激进），False=单窗口轮询
    """
    if not drivers:
        print("错误: 需要提供 WebDriver 实例。")
        return

    if dual_mode and len(drivers) < 2:
        print("警告: dual_mode 需要至少 2 个 driver，回退为单窗口模式。")
        dual_mode = False

    # 每个窗口独立队列（避免线程竞争）
    courses = list(courseList.keys())
    queue_poll = Queue()
    queue_aggressive = Queue()
    for c in courses:
        queue_poll.put(c)
        queue_aggressive.put(c)

    instances = []
    threads = []

    # 窗口 1：轮询模式
    instance_poll = GetCourse(courseList, drivers[0], fuzzy_match=Properties.FUZZY_MATCH)
    instances.append(instance_poll)
    thread_poll = Thread(target=instance_poll.run_poll, args=(queue_poll,), name="Poll")
    threads.append(thread_poll)
    print("已创建 [轮询] 线程（窗口 1）")

    if dual_mode:
        # 窗口 2：激进模式
        instance_agg = GetCourse(courseList, drivers[1], fuzzy_match=Properties.FUZZY_MATCH)
        instances.append(instance_agg)
        thread_agg = Thread(target=instance_agg.run_aggressive, args=(queue_aggressive,), name="Aggressive")
        threads.append(thread_agg)
        print("已创建 [激进] 线程（窗口 2）")

    for thread in threads:
        print(f"正在启动线程: {thread.name}")
        thread.start()

    for thread in threads:
        thread.join()

    print("所有线程已完成。")


if __name__ == '__main__':
    # 加载配置
    config = load_config()
    Properties.init_from_config(config)

    driver_count = 2 if Properties.dual_mode else 1
    props = Properties(count=driver_count)
    drivers = props.drivers

    if drivers:
        try:
            print("--- 启动选课脚本 ---")
            print(f"双窗口模式: {'开' if Properties.dual_mode else '关'}")
            print(f"课程列表: {Properties.courseList}")
            print(f"开始时间: {Properties.begin}")
            print(f"模糊匹配: {'开' if Properties.FUZZY_MATCH else '关'}")
            print(f"连击次数: {Properties.CLICK_BURST}")
            run(Properties.courseList, drivers, dual_mode=Properties.dual_mode)
        except KeyboardInterrupt:
            print("\n用户中断，正在退出...")
        finally:
            print("--- 正在关闭浏览器 ---")
            # 主 driver 负责关闭浏览器，附加 driver 只关闭自身连接
            for i, d in enumerate(drivers):
                try:
                    d.quit()
                except Exception:
                    pass  # 共享实例时第二个 quit 可能抛异常，忽略
    else:
        print("未能初始化 WebDriver。程序退出。")


