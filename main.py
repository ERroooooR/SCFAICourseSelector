import os
import time
from queue import Queue
from datetime import datetime
from threading import Thread
try:
    from selenium import webdriver
except ImportError:
    print("未找到 selenium 库，正在尝试安装...")
    os.system('pip install selenium')
    from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException


class Properties:
    # 开始抢课时间
    begin = datetime.strptime("2025-9-24 17:52:00", "%Y-%m-%d %H:%M:%S")
    # 延迟时间，防止页面未加载完成
    DELAY_TIME = 0.8

    # 自定义课程列表  课程名:课程班号
    courseList = {
        "体育1": "010567-039",
    }
    # Chrome 浏览器可执行文件路径
    google_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    # ChromeDriver 路径 (建议使用绝对路径)
    chromedriver_path = r"chromedriver.exe"

    def __init__(self):
        from selenium.webdriver.chrome.service import Service
        service = Service(self.chromedriver_path)
        options = Options()
        options.binary_location = self.google_path
        try:
            driver = webdriver.Chrome(options=options, service=service)
        except Exception as e:
            print(f"初始化 WebDriver 时出错: {e}")
            print("驱动异常，正在尝试下载或更新...")
            try:
                from updateDriver import update_driver
                update_driver()
                print("驱动下载/更新完成。")
                # 重新创建 Service 对象，确保使用更新后的驱动
                service = Service(self.chromedriver_path)
                driver = webdriver.Chrome(options=options, service=service)
                print("WebDriver 初始化成功。")
            except Exception as update_e:
                print(f"驱动下载/更新失败: {update_e}")
                raise  
        self.driver = driver


class GetCourse:
    # 登录页面URL
    login_url = "http://ids.scfai.edu.cn/#/login"
    # 登录成功后跳转的仪表盘URL
    dashboard_url = "http://ids.scfai.edu.cn/#/dashboard"
    # 选课系统主页URL
    course_selection_url = "https://jwjx.scfai.edu.cn/enroll/Home"

    def __init__(self, courseList, driver=None):
        self.driver = driver
        self.courseList = courseList
        self.had_Selected_items = set()

    def wait(self, sensitivity=1, *element):
        """ 隐式等待 - 单元素 """
        while sensitivity > 0:
            try:
                webWait = WebDriverWait(self.driver, 4)
                wait = webWait.until(EC.presence_of_element_located(element))
                return wait
            except TimeoutException:
                sensitivity -= 1
                try:
                    ele = self.driver.find_element(*element)
                    self.driver.execute_script("arguments[0].scrollIntoView();", ele)
                except Exception as e:
                    print(f"元素未找到，正在重试... 错误: {e}")
                print("正在重试单元素等待...")
        raise NoSuchElementException("重试后仍未找到元素")

    def waits(self, *element):
        """ 隐式等待 - 多元素 """
        count = 0
        while True:
            try:
                webWait = WebDriverWait(self.driver, 4)
                wait = webWait.until(EC.presence_of_all_elements_located(element))
                return wait
            except TimeoutException:
                count += 1
                if count % 3 == 0:
                    print("为查找多个元素而刷新页面...")
                    self.driver.refresh()

    def do(self, func):
        """ 从主界面进入选课界面 """
        target_url = self.course_selection_url
        if self.driver.current_url != target_url:
            print(f"正在导航至选课页面: {target_url}")
            self.driver.get(target_url)
        xpathStr = f"//div[contains(@class,\"select-model\")]//div[contains(@class,\"select-list-model\") or contains(@class,\"selected-course-info\")]//button[.//span[contains(text(), \"{func}\")]]"
        
        max_retries = 1 # 设置最大重试次数
        retry_count = 0
        while retry_count < max_retries:
            try:
                self.wait(2, By.XPATH, xpathStr)
                # 等待开始时间
                while datetime.now() <= Properties.begin:
                    time.sleep(0.1)  # 短暂休眠避免CPU占用过高
                print(f"时间到，尝试点击 '{func}' 按钮。")
                elements = self.driver.find_elements(By.XPATH, xpathStr)
                if elements:
                    elements[-1].click()  # 点击最后一个匹配的按钮
                    print(f"已点击 '{func}' 按钮。")
                    return True # 成功点击后返回
                else:
                    raise NoSuchElementException("未找到按钮元素")
            except ElementNotInteractableException as e:
                print(f"元素不可交互 (尝试第 {retry_count + 1} 次): {e}")
                # 尝试点击第一个元素
                try:
                    elements = self.driver.find_elements(By.XPATH, xpathStr)
                    if elements:
                        elements[0].click()
                        print(f"因交互性问题，已点击第一个 '{func}' 按钮。")
                        return True # 成功点击后返回
                except Exception as inner_e:
                    print(f"点击第一个元素也失败: {inner_e}")
            except Exception as e:
                print(f"'do' 方法中出错 (尝试第 {retry_count + 1} 次): {e}。正在重试...")
            
            retry_count += 1
            if retry_count < max_retries:
                 print(f"等待 {Properties.DELAY_TIME}s 后重试...")
                 time.sleep(Properties.DELAY_TIME)
                 # 重新加载页面
                 self.driver.get(target_url)
                 time.sleep(Properties.DELAY_TIME) # 等待页面加载

        print(f"'do' 方法达到最大重试次数 ({max_retries})，未能成功点击按钮。")
        return False # 达到最大重试次数仍未成功

    def close(self):
        """ 关闭可能的弹窗 """
        try:
            close_button = self.driver.find_element(By.XPATH, "//i[@aria-label=\"图标: close\"]")
            close_button.click()
            print("已关闭一个弹窗。")
        except Exception as e:
            # print(f"没有弹窗可关闭或关闭时出错: {e}")
            pass

    def select(self, name):
        """ 执行选课操作 """
        max_retries = 1
        retry_count = 0
        while retry_count < max_retries:
            try:
                # 选择课程种类
                course_link = self.wait(2, By.XPATH, f"//a[@title=\"{name}\"]")
                course_link.click()
                print(f"已点击课程类别: {name}")

                # 等待并选择课程号
                xpath_CID = f"//tbody[@class=\"ant-table-tbody\"]/tr[.//span[text()=\"{self.courseList[name]}\"]]/td[last()]/span"
                self.wait(2, By.XPATH, xpath_CID)
                try:
                    selectable_span = self.driver.find_element(By.XPATH, f"{xpath_CID}[./label]")
                    selectable_span.click()
                    print(f"已选择课程: {name} - {self.courseList[name]}")
                except NoSuchElementException:
                    print(f"课程 {name} ({self.courseList[name]}) 无法选择 (可能已选或已满)。")
                    self.close()
                    return False # 课程不可选，返回False
                
                # 初步确认 
                confirm_button_1 = self.driver.find_element(By.XPATH,
                                                            f"//div[@class=\"select-class-info-modal\"]//button[.//span[contains(text(),\"选\")]]")
                confirm_button_1.click()
                print("已点击初步选课确认。")
                
                # 进一步确认 
                confirm_button_2 = self.driver.find_element(By.XPATH,
                                                            f"//div[@class=\"ant-modal-confirm-btns\"]//button[.//span[contains(text(), \"确\")]]")
                confirm_button_2.click()
                print("已点击最终确认。")
                
                self.close() 
                return True # 成功完成选课流程

            except Exception as e:
                retry_count += 1
                print(f"选择课程 {name} 时出错 (尝试第 {retry_count} 次)，正在刷新并重试... 错误: {e}")
                if retry_count < max_retries:
                    self.driver.refresh()
                    time.sleep(Properties.DELAY_TIME) # 刷新后稍等
                else:
                    print(f"选择课程 {name} 达到最大重试次数，可能失败。")
                    
        self.close() 
        return False 

    def isSelected(self, name):
        """ 判断是否成功选到目标课程 """
        self.had_Selected_items.clear()  
        try:
            # 查找所有已选课程名称
            selected_elements = self.waits(By.XPATH, "//div[@id='resultList']//span[@class='resultList-name']")
            for element in selected_elements:
                # 获取文本内容
                course_title = element.text.strip()
                if course_title:
                    self.had_Selected_items.add(course_title)
            print(f"当前已选课程: {self.had_Selected_items}")
            print(f"剩余待选课程: {set(self.courseList.keys()) - self.had_Selected_items}")
        except Exception as e:
            print(f"检查已选课程时出错: {e}")

        if name in self.had_Selected_items:
            print(f"课程 {name} 已成功选择！")
            return True
        return False

    def circle(self, courseQueue):
        """ 循环尝试选课 """
        temp_courses_to_check = [] 
        while not courseQueue.empty():
            courseName = courseQueue.get()
            print(f"正在尝试选择: {courseName}")
            select_result = self.select(courseName)
            # 无论 select 成功与否，都将课程名暂存，稍后检查 isSelected
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

        print("等待后刷新页面...")
        time.sleep(0.8)
        print("正在刷新页面...")
         self.driver.refresh()
        print("刷新后等待页面加载...")
        time.sleep(0.8)  # 等待页面加载稳定

        print("重复选课循环...")
        return self.circle(courseQueue)  

    def run_rand(self, courseQueue):
        """ 主运行逻辑 """
        self.driver.maximize_window()
        print(f"1. 正在导航至登录页面: {self.login_url}")
        print("   请在打开的浏览器窗口中手动登录。")
        self.driver.get(self.login_url)  # 导航到登录页面
        print(f"2. 等待成功登录并跳转至: {self.dashboard_url}")
        while True:
            current_url = self.driver.current_url
            if current_url.startswith(self.dashboard_url):
                print("   检测到手动登录成功并已跳转至仪表盘。")
                break
            else:
                print(f"   当前 URL: {current_url}。仍在等待登录完成...")
                time.sleep(2)

        # 导航到选课系统
        print(f"3. 正在导航至选课系统: {self.course_selection_url}")
        self.driver.get(self.course_selection_url)
        print("   导航完成。等待页面加载...")
        time.sleep(Properties.DELAY_TIME)  # 等待选课页面加载

        # 进入选课操作
        print("4. 即将进行选课操作。")
        if self.do("选"): # 检查 do 方法是否成功
            print(f"抢课时间已到 ({Properties.begin}), 开始执行选课操作...")
            time.sleep(Properties.DELAY_TIME)
            # 开始循环选课
            result = self.circle(courseQueue)
            if result:
                print("所有课程均已处理并确认（或已无余课）。")
            else:
                print("选课循环结束，但可能有课程未选上。")
        else:
            print("无法进入选课操作，可能是按钮点击失败。")


def run(courseList, thread_num, driver=None):
    """ 启动选课线程 """
    if not driver:
        print("错误: 需要提供 WebDriver 实例。")
        return

    # 创建一个队列来存放课程
    queue = Queue()

    threads = []
    instances = [] # 存储 GetCourse 实例

    # 将所有课程放入队列
    for course_name in courseList.keys():
        queue.put(course_name)

    # 为每个线程创建 GetCourse 实例并启动线程
    for i in range(thread_num):
        instance = GetCourse(courseList, driver)
        instances.append(instance) # 保存实例引用
        thread = Thread(target=instance.run_rand, args=(queue,))
        threads.append(thread)
        print(f"已创建线程 {i+1}")

    # 启动所有线程
    for thread in threads:
        print(f"正在启动线程: {thread.name}")
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    print("所有线程已完成。")


if __name__ == '__main__':
    props = Properties() 
    driver = props.driver 

    if driver:
        try:
            print("--- 启动选课脚本 ---")
            run(Properties.courseList, thread_num=1, driver=driver)
        finally:
            print("--- 正在关闭浏览器 ---")
            driver.quit()
    else:
        print("未能初始化 WebDriver。程序退出。")


