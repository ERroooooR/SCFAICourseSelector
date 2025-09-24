# SCFAI Course Selector

四川美术学院自动选课 (SCFAI Course Selector) 是一个基于Python和Selenium的自动化选课工具，旨在帮助学生更高效地选择课程。

## 功能特点

- 根据预设课程列表自动选课
- 支持定时抢课功能
- 多线程处理提高选课效率
- 自动处理弹窗和异常情况

## 环境要求

- Windows/Linux 操作系统
- Google Chrome浏览器
- Python 3.6+

## 安装指南

1. 安装Google Chrome浏览器（请从[官网](https://www.google.com/intl/zh-CN/chrome/)下载，不要修改默认安装目录）
2. 安装Python
3. 运行create_venv_windows.bat创建Python虚拟环境：
4. 配置课程列表：
   打开`main.py`文件，修改`courseList`字典，添加需要选择的课程：

```python
courseList = {
    "体育1": "010567-039",
    # 添加更多课程，格式为 "课程名称": "课程班号"
}
```

## 使用方法

1. 配置选课时间： 在[main.py]()中的[Properties]()类里修改[begin]()变量，设置抢课开始时间：

```python
begin = datetime.strptime("2025-09-24 17:52:00", "%Y-%m-%d %H:%M:%S")
```

2. 运行选课程序：

```
run_app_in_venv_windows.bat
```

3. 程序启动后会自动打开浏览器，您需要在登录页面手动输入账号密码登录
4. 系统会自动导航到选课页面并在设定时间开始选课

## 配置说明

### 主要配置项

在[main.py]()的[Properties]()类中可以修改以下配置：

* [begin](): 抢课开始时间
* [DELAY\_TIME](): 页面加载延迟时间
* [courseList](): 需要选择的课程列表
* [google\_path](): Chrome浏览器路径（默认路径通常无需修改）
* [chromedriver\_path](): ChromeDriver路径（默认无需修改）

## 注意事项

1. 请确保Chrome浏览器安装在默认路径，否则需要修改[google\_path]()配置
2. 如果遇到ChromeDriver版本不匹配问题，程序会自动尝试下载更新
3. 请提前登录测试账号密码，确保能正常访问选课系统
4. 建议在选课开始前几分钟运行程序，完成登录和页面加载
5. 不要频繁运行程序，避免给选课系统造成过大压力

## 免责声明

本工具仅供学习交流使用，请遵守学校相关规定，合理使用自动化工具。使用本工具造成的任何后果由使用者自行承担。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 许可证

本项目基于MIT许可证开源。
