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
# DOM 工具
# ============================================================

def _cell_text(cell):
    """读取表格单元格文本，优先用 textContent（兼容不可见元素）。"""
    try:
        return (cell.get_attribute("textContent") or "").strip()
    except Exception:
        return (cell.text or "").strip()


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
    api_mode = bool(cfg.get("api_mode", False))
    auto_login = bool(cfg.get("auto_login", False))
    username = cfg.get("username", "").strip()
    password = cfg.get("password", "").strip()
    courses = cfg.get("courses", {})

    # 清理 courses 中的 _comment 等非课程条目（键以 _ 开头的跳过）
    courses = {k: v for k, v in courses.items() if not k.startswith("_")}

    # 标准化 course 值：字符串 → {label/class_id} 对象
    normalized = {}
    for k, v in courses.items():
        if isinstance(v, str):
            v = v.strip()
            normalized[k] = {"course_code": "", "label": v, "class_id": "", "teacher": ""}
        elif isinstance(v, dict):
            normalized[k] = {
                "course_code": (v.get("course_code", "") or "").strip(),
                "label": (v.get("label", "") or "").strip(),
                "class_id": (v.get("class_id", "") or "").strip(),
                "teacher": (v.get("teacher", "") or "").strip(),
            }
        else:
            normalized[k] = {"course_code": "", "label": "", "class_id": "", "teacher": ""}
    courses = normalized

    return {
        "begin_time": begin_time,
        "delay_time": delay,
        "click_burst": click_burst,
        "chrome_path": chrome_path or None,
        "fuzzy_match": fuzzy_match,
        "dual_mode": dual_mode,
        "api_mode": api_mode,
        "auto_login": auto_login,
        "username": username,
        "password": password,
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
        "api_mode": False,
        "auto_login": False,
        "username": "",
        "password": "",
        "courses": {
            "体育2": {
                "course_code": "",
                "label": "羽毛球",
                "class_id": "",
                "teacher": ""
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
        cls.api_mode = bool(cfg.get("api_mode", False))
        cls.auto_login = bool(cfg.get("auto_login", False))
        cls.login_username = cfg.get("username", "").strip()
        cls.login_password = cfg.get("password", "").strip()
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

    def __init__(self, courseList, driver=None, fuzzy_match=False, api_selector=None):
        self.driver = driver
        self.courseList = courseList
        self.fuzzy_match = fuzzy_match
        self.api_selector = api_selector
        self.web_wait = WebDriverWait(self.driver, 4)

    def _course_title_xpath(self, name, course_code=""):
        """根据模糊/精确模式生成课程标题 XPath。引号自动转义。
        
        当提供 course_code 时，同时匹配课程代码列，用于区分同名不同码的课程。
        """
        safe = name.replace('"', '').replace("'", '')
        if self.fuzzy_match:
            base = f'//a[contains(@title, "{safe}")]'
        else:
            base = f'//a[@title="{safe}"]'

        if course_code:
            safe_code = course_code.replace('"', '').replace("'", '')
            # 匹配同一行同时包含课程名和课程代码
            return (
                f'//tr[td//a[contains(@title, "{safe}")]'
                f' and contains(td[2]//text(), "{safe_code}")]'
                f'//a[contains(@title, "{safe}")]'
            )
        return base

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
        """ 执行选课操作 — API 模式下走 JSON 解析，否则走 DOM 点击。

        两层独立匹配：
        1. 课程名（name）→ 主列表定位课程（受 fuzzy_match 控制）
        2. label/class_id/teacher → Modal 内筛选教学班（各自模糊匹配，OR 关系）
        """
        target = self.courseList.get(name, {"label": "", "class_id": "", "teacher": ""})

        # ── API 模式：跳过 DOM，直接 JSON 选课 ──
        if self.api_selector:
            success, msg = self.api_selector.find_and_select(
                name, target, fuzzy_course=self.fuzzy_match
            )
            if success:
                print(f"[API] ✓ {name}: {msg}")
                return True
            else:
                print(f"[API]   {name}: {msg}")
                return False

        # ── DOM 模式（原逻辑）──
        # 1. 点击课程链接打开 Modal
        course_code = target.get("course_code", "") or ""
        course_link = self.wait(2, By.XPATH, self._course_title_xpath(name, course_code))
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

        target_label = (target.get("label", "") or "").strip()
        target_cid  = (target.get("class_id", "") or "").strip()
        target_teacher = (target.get("teacher", "") or "").strip()

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

        print(f"  找到 {len(rows)} 个教学班，label='{target_label}' class_id='{target_cid}' teacher='{target_teacher}'")

        # 3. 遍历教学班行，找第一个可选的
        for idx, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 9:
                continue

            class_id_text = _cell_text(cells[0])
            label_text = _cell_text(cells[5]) if len(cells) > 5 else ""
            teacher_text = _cell_text(cells[3]) if len(cells) > 3 else ""
            capacity_text = _cell_text(cells[4]) if len(cells) > 4 else ""

            # ── 匹配判断 ──
            matched = False
            reason_parts = []

            if not target_label and not target_cid and not target_teacher:
                matched = True
                reason_parts.append("自动")
            else:
                if target_label and target_label in label_text:
                    matched = True
                    reason_parts.append(f"标签含'{target_label}'")
                if target_cid and target_cid in class_id_text:
                    matched = True
                    reason_parts.append(f"班号含'{target_cid}'")
                if target_teacher and target_teacher in teacher_text:
                    matched = True
                    reason_parts.append(f"教师含'{target_teacher}'")
            match_info = f"班号={class_id_text} 教师={teacher_text} 标签={label_text}"

            if not matched:
                print(f"    班 {idx+1}: 跳过（不匹配） {match_info}")
                continue

            # ── 过滤条件：匹配的行也要检查是否可选 ──
            status_text = _cell_text(cells[8])

            if status_text in ("已选", "容量已满", "教学班已锁定"):
                print(f"    班 {idx+1}: 跳过（匹配但{status_text}） {match_info}")
                continue

            checkboxes = cells[8].find_elements(By.XPATH, ".//input[@type='checkbox']")
            if not checkboxes:
                print(f"    班 {idx+1}: 跳过（匹配但无选择框） {match_info}")
                continue

            conflicts = cells[0].find_elements(By.XPATH, ".//*[contains(@aria-label,'exclamation-circle')]")
            if conflicts:
                print(f"    班 {idx+1}: 跳过（匹配但时间冲突） {match_info}")
                continue

            locks = cells[0].find_elements(By.XPATH, ".//*[contains(@aria-label,'lock')]")
            if locks:
                print(f"    班 {idx+1}: 跳过（匹配但已锁定） {match_info}")
                continue

            # ── 执行选择 ──
            reason = " + ".join(reason_parts)
            print(f"    班 {idx+1}: ✓ {reason} → {match_info} 容量={capacity_text}")
            try:
                # 滚动到 checkbox 可见区域
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center',inline:'center'});",
                    checkboxes[0]
                )
                checkboxes[0].click()

                confirm_1 = self.driver.find_element(By.XPATH,
                    "//div[@class='select-class-info-modal']"
                    "//button[.//span[contains(text(),'选')]]")
                confirm_1.click()
                print("    已点击初步选课确认。")

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
        print(f"  课程 {name}: 无可用教学班（label='{target_label}' class_id='{target_cid}' teacher='{target_teacher}'）。")
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
            # ── 主线程：执行登录 ──
            self.driver.maximize_window()
            print(f"[{label}] 1. 导航至登录页面: {self.login_url}")
            self.driver.get(self.login_url)

            # ── 自动登录 ──
            if Properties.auto_login and Properties.login_username and Properties.login_password:
                print(f"[{label}]    自动登录中 ({Properties.login_username})...")
                try:
                    # 等待登录表单
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//input[@placeholder and contains(@placeholder,'学工号')]")
                        )
                    )
                    # 确保在"账号登录" tab（Element UI: el-tabs__item）
                    account_tab = self.driver.find_elements(
                        By.XPATH, "//*[@role='tab' and contains(.,'账号登录')]"
                    )
                    if account_tab and account_tab[0].get_attribute("aria-selected") != "true":
                        account_tab[0].click()
                        time.sleep(0.3)

                    # 填入用户名
                    user_input = self.driver.find_element(
                        By.XPATH, "//input[@placeholder and contains(@placeholder,'学工号')]"
                    )
                    user_input.clear()
                    user_input.send_keys(Properties.login_username)

                    # 填入密码
                    pwd_input = self.driver.find_element(
                        By.XPATH, "//input[@type='password' or contains(@placeholder,'密码')]"
                    )
                    pwd_input.clear()
                    pwd_input.send_keys(Properties.login_password)

                    # 点击登录按钮
                    login_btn = self.driver.find_element(
                        By.XPATH, "//button[.//span[text()='登录'] or contains(text(),'登录')]"
                    )
                    login_btn.click()
                    print(f"[{label}]    已点击登录按钮，等待跳转...")
                except Exception as e:
                    print(f"[{label}]    自动登录失败: {e}，请手动登录")
            else:
                print(f"[{label}]    请在浏览器中手动登录（只需一次）。")

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
                    code = self.courseList.get(courseName, {}).get("course_code", "") or ""
                    link = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located(
                            (By.XPATH, self._course_title_xpath(courseName, code))
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


# ============================================================
# API 直连选课 — 绕过 DOM，直接 JSON 解析 + HTTP POST
# ============================================================

class APISelector:
    """通过学校选课 API 直接选课（使用浏览器 fetch，无需 token）。

    所有 API 调用通过 driver.execute_async_script 在浏览器 JS 上下文中执行，
    自动继承页面的 Authorization / Cookie，无需手动提取 token。

    用法:
        api = APISelector(driver)
        api.find_and_select("体育2", {"label": "羽毛球", "teacher": "纪超香"})
    """

    # 限速常量（服务器对 POST /student/select 有频率限制）
    POST_COOLDOWN = 1.0       # 两次 POST 间最小间隔（秒）
    POST_BACKOFF_MAX = 5.0    # 遇到限速时最大退避秒数
    RATE_LIMIT_MSG = "请求过于频繁"  # 服务器限速提示

    def __init__(self, driver):
        self.driver = driver
        self._last_post_time = 0
        self._cached_token = None
        self._post_lock = __import__('threading').Lock()

    # ── Token ──

    def _get_token(self):
        """从浏览器 localStorage 读取 Bearer token。"""
        token = self.driver.execute_script(
            "var t = localStorage.getItem('cqu_edu_ACCESS_TOKEN') || "
            "localStorage.getItem('cqu_edu_CURRENT_TOKEN');"
            "if (t) { try { return JSON.parse(t); } catch(e) { return t; } }"
            "return null;"
        )
        if token:
            print(f"[API] Token 获取成功: {token[:20]}...")
            return token
        print("[API] Token 未找到，请确认已登录。")
        return None

    def _browser_fetch(self, url, method="GET", body=None):
        """在浏览器中执行 fetch 并返回 JSON。自动注入 Bearer token。"""
        if self._cached_token is None:
            self._cached_token = self._get_token()
        token = self._cached_token

        auth_part = f"'Authorization':'Bearer {token}'," if token else ""
        body_part = f"body:JSON.stringify({body})," if body else ""

        wrapped = f"""
        var done = arguments[arguments.length - 1];
        fetch('{url}', {{
            method: '{method}',
            credentials: 'include',
            headers: {{ {auth_part} 'Content-Type': 'application/json', 'Accept': 'application/json' }},
            {body_part}
        }}).then(function(r) {{
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }}).then(function(data) {{
            done(JSON.stringify({{ok: true, data: data}}));
        }}).catch(function(err) {{
            done(JSON.stringify({{ok: false, error: err.message || String(err)}}));
        }});
        """
        try:
            raw = self.driver.execute_async_script(wrapped)
            result = json.loads(raw)
            if result.get("ok"):
                return result.get("data")
            else:
                err = result.get("error", "")
                if "HTTP 401" in err and self._cached_token:
                    # token 可能过期，清除缓存重新读取 localStorage
                    print(f"[API] 401，Token 可能过期，重新读取...")
                    self._cached_token = None
                    return None
                print(f"[API] fetch 失败: {err}")
                return None
        except Exception as e:
            print(f"[API] execute_async_script 异常: {e}")
            return None

    # ── API 端点 ──

    def get_course_list(self, selection_source="主修"):
        """获取课程列表，返回扁平化数组 [{id, name, codeR(→str), ...}]。"""
        from urllib.parse import quote
        url = f"/api/enrollment/enrollment/course-list?selectionSource={quote(selection_source)}"
        resp = self._browser_fetch(url, "GET")
        if not resp:
            return []
        data_list = resp.get("data", [])
        courses = []
        for area in data_list:
            for c in area.get("courseVOList", []):
                # codeR 可能是整数，统一转字符串
                if "codeR" in c:
                    c["codeR"] = str(c["codeR"])
                courses.append(c)
        return courses

    def get_course_details(self, course_id, selection_source="主修"):
        """获取教学班详情，返回 selectCourseVOList。"""
        from urllib.parse import quote
        url = f"/api/enrollment/enrollment/courseDetails/{course_id}?selectionSource={quote(selection_source)}"
        data = self._browser_fetch(url, "GET")
        if data and "selectCourseListVOs" in data:
            vos = data["selectCourseListVOs"]
            if vos and "selectCourseVOList" in vos[0]:
                return vos[0]["selectCourseVOList"]
        return []

    def submit_selection(self, course_name, course_code, course_id, class_id,
                         selection_source="主修"):
        """提交选课请求（内置限速保护 + 自动退避）。

        返回: (success: bool, message: str)
        """
        # 限速保护（线程安全）
        with self._post_lock:
            elapsed = time.time() - self._last_post_time
            if elapsed < self.POST_COOLDOWN:
                time.sleep(self.POST_COOLDOWN - elapsed)
            self._last_post_time = time.time()

        for attempt in range(1, 4):
            data = self._browser_fetch(
                "/api/enrollment/enrollment/student/select", "POST",
                json.dumps({
                    "courses": [{
                        "courseName": course_name,
                        "courseCode": course_code,
                        "courseId": str(course_id),
                        "classes": [{"classIds": [str(class_id)], "fakeClassTypeList": []}],
                    }],
                    "selectionSource": selection_source,
                })
            )

            if data is None:
                return False, "网络错误"

            msg = data.get("msg", data.get("message", ""))
            if data.get("ok") is True or data.get("status") == "success":
                return True, "选课成功"

            if self.RATE_LIMIT_MSG in msg:
                wait = min(self.POST_COOLDOWN * (2 ** attempt), self.POST_BACKOFF_MAX)
                print(f"[API]   限速退避: 等待 {wait:.1f}s 后重试 ({attempt}/3)")
                time.sleep(wait)
                continue

            return False, msg

        return False, "请求过于频繁，已达最大重试"


    # ── 核心匹配 ──

    def find_and_select(self, course_name, target, selection_source="主修",
                        fuzzy_course=True):
        """完整选课流程（API 模式）。

        参数:
            course_name:  课程名（如"体育2"）
            target:       {"label": "...", "class_id": "...", "teacher": "..."}
            fuzzy_course: 课程名模糊匹配

        返回:
            (True, msg)  选课成功
            (False, msg) 失败原因
        """
        target_label = (target.get("label", "") or "").strip()
        target_cid = (target.get("class_id", "") or "").strip()
        target_teacher = (target.get("teacher", "") or "").strip()
        target_code = (target.get("course_code", "") or "").strip()

        # 1. 从课程列表中找到 courseId 和 courseCode
        course_list = self.get_course_list(selection_source)
        if not course_list:
            return False, "无法获取课程列表"

        course_id = None
        course_code = None
        course_name_full = None
        candidates = []

        for c in course_list:
            c_name = c.get("name", "")
            c_code = str(c.get("codeR", ""))
            name_ok = (fuzzy_course and course_name in c_name) or (not fuzzy_course and c_name == course_name)
            code_ok = (not target_code) or (target_code in c_code)
            if name_ok and code_ok:
                candidates.append(c)

        if not candidates:
            reason = f"课程 '{course_name}'"
            if target_code:
                reason += f" (code='{target_code}')"
            return False, f"{reason} 不在列表中"
        if len(candidates) > 1:
            names = [f"{c['name']}({c.get('codeR','?')})" for c in candidates]
            print(f"[API] ⚠ 课程 '{course_name}' 命中多项: {names}")
            # 优先级: 精确名+精确码 > 精确码 > 精确名 > 首个
            exact = next((c for c in candidates
                         if c["name"] == course_name and c.get("codeR") == target_code), None)
            if not exact and target_code:
                exact = next((c for c in candidates if c.get("codeR") == target_code), None)
            if not exact and not target_code:
                exact = next((c for c in candidates if c["name"] == course_name), None)
            if exact:
                candidates = [exact]
                print(f"[API]   → 选定: {exact['name']}({exact.get('codeR','?')})")

        c = candidates[0]
        course_id = c["id"]
        course_code = c.get("codeR", c.get("code", ""))
        course_name_full = c["name"]

        print(f"[API] 找到课程: {course_name_full} (id={course_id}, code={course_code})")

        # 2. 获取教学班详情
        classes = self.get_course_details(course_id, selection_source)
        if not classes:
            return False, "无法获取教学班详情（可能是非选课时间）"

        print(f"[API] 找到 {len(classes)} 个教学班")

        # 3. 过滤 + 匹配
        matched_log = []
        for cls in classes:
            labels = cls.get("classTagNameList", [])
            instructor = cls.get("instructorNames", "")
            class_nbr = cls.get("classNbr", "")
            selected_num = cls.get("selectedNum", 0)
            capacity = cls.get("stuCapacity", 999)
            class_id = cls.get("id", "")

            # 过滤不可选条件
            skip_reason = None
            if cls.get("errorList"):
                skip_reason = "时间冲突"
            elif cls.get("selectedFlag"):
                skip_reason = "已选"
            elif selected_num >= capacity:
                skip_reason = "容量已满"
            elif cls.get("selectCourseLocked"):
                skip_reason = "已锁定"

            if skip_reason:
                matched_log.append(
                    f"  跳过 {class_nbr}: {skip_reason} "
                    f"教师={instructor} 标签={labels} 容量={selected_num}/{capacity}"
                )
                continue

            # 匹配逻辑（OR 关系）
            matched = False
            if not target_label and not target_cid and not target_teacher:
                matched = True

            if target_label and any(target_label in lbl for lbl in labels):
                matched = True
            if target_cid and target_cid in class_nbr:
                matched = True
            if target_teacher and target_teacher in instructor:
                matched = True

            if matched:
                # 提交选课！
                if matched_log:
                    print("\n".join(matched_log[-10:]))
                print(f"  ✓ 选定: {class_nbr} 教师={instructor} "
                      f"标签={labels} 容量={selected_num}/{capacity}")

                success, msg = self.submit_selection(
                    course_name_full, course_code, course_id, class_id, selection_source
                )
                return success, msg
            else:
                matched_log.append(
                    f"  跳过 {class_nbr}: 不匹配 "
                    f"教师={instructor} 标签={labels} 容量={selected_num}/{capacity}"
                )

        # 所有都跳过/不匹配
        print("\n".join(matched_log[-20:]))
        return False, f"无可用教学班（label='{target_label}' class_id='{target_cid}' teacher='{target_teacher}'）"


def run(courseList, drivers, dual_mode=True, api_mode=False):
    """ 启动选课。

    drivers: WebDriver 实例列表
    dual_mode: True=双窗口（轮询+激进），False=单窗口轮询
    api_mode: True=API 直连选课（JSON 解析，快 10-100 倍）
    """
    if not drivers:
        print("错误: 需要提供 WebDriver 实例。")
        return

    if dual_mode and len(drivers) < 2:
        print("警告: dual_mode 需要至少 2 个 driver，回退为单窗口模式。")
        dual_mode = False

    # ── API 模式初始化 ──
    api = None
    if api_mode:
        print("=== API 直连模式 ===")
        api = APISelector(drivers[0])

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
    instance_poll = GetCourse(courseList, drivers[0],
                              fuzzy_match=Properties.FUZZY_MATCH,
                              api_selector=api)
    instances.append(instance_poll)
    thread_poll = Thread(target=instance_poll.run_poll, args=(queue_poll,), name="Poll")
    threads.append(thread_poll)
    print("已创建 [轮询] 线程（窗口 1）")

    if dual_mode:
        # 窗口 2：激进模式
        instance_agg = GetCourse(courseList, drivers[1],
                                 fuzzy_match=Properties.FUZZY_MATCH,
                                 api_selector=api)
        instances.append(instance_agg)
        thread_agg = Thread(target=instance_agg.run_aggressive,
                           args=(queue_aggressive,), name="Aggressive")
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
            print(f"API 模式: {'开' if Properties.api_mode else '关'}")
            run(Properties.courseList, drivers,
                dual_mode=Properties.dual_mode,
                api_mode=Properties.api_mode)
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


