# SCFAI 自动选课工具

四川美术学院智慧教务自动选课脚本，基于 Python 与 Selenium。支持多账号并发、独立浏览器数据目录、自动登录、DOM 选课、API 选课和混合模式。

> 本项目仅供学习交流。请遵守学校系统规则，使用后果自行承担。

## 功能概览

- 多账号并发运行，每个账号使用独立 Chrome 用户数据目录，登录态互不影响。
- 支持自动登录，也支持首次手动登录后复用本地 Cookie。
- 支持三种运行模式：纯 DOM、纯 API、混合模式。
- 支持按课程代码、标签、教学班号、教师匹配目标教学班。
- ChromeDriver 可自动检测并下载到 `driver/` 目录。
- 任务结束后保留浏览器窗口，便于查看结果。

## 快速开始

1. 复制 `config.example.json` 为 `config.json`。
2. 编辑 `config.json`，填入账号、密码、开始时间和目标课程。
3. 首次运行先完成环境安装。
4. 启动脚本等待选课时间，到点后自动执行。

Windows:

```bat
setup.bat
run_app_in_venv_windows.bat
```

Linux / macOS:

```bash
bash setup.sh
bash run_app.sh
```

## 配置示例

```json
{
    "global": {
        "begin_time": "2025-09-25 13:00:30",
        "delay_time": 0.8,
        "click_burst": 8,
        "chrome_path": "",
        "fuzzy_match": true
    },
    "accounts": [
        {
            "name": "张三",
            "username": "2025211656",
            "password": "你的密码",
            "auto_login": true,
            "dual_mode": true,
            "api_mode": false,
            "mixed_mode": true,
            "courses": {
                "体育2": {
                    "course_code": "",
                    "label": "羽毛球",
                    "class_id": "",
                    "teacher": "纪超香"
                }
            }
        }
    ]
}
```

## 全局配置

| 字段 | 说明 |
|---|---|
| `begin_time` | 抢课开始时间，格式为 `YYYY-MM-DD HH:MM:SS` |
| `delay_time` | 页面跳转或刷新后的等待秒数 |
| `click_burst` | DOM 模式下单门课程每轮最大点击次数 |
| `chrome_path` | Chrome 可执行文件路径，留空则自动检测 |
| `fuzzy_match` | 是否启用课程名模糊匹配 |

## 账号配置

| 字段 | 说明 |
|---|---|
| `name` | 日志中显示的账号名称 |
| `username` | 学号 |
| `password` | 密码 |
| `auto_login` | 是否自动填写账号密码并登录 |
| `dual_mode` | 是否启用双 Tab 并行 |
| `api_mode` | 是否使用纯 API 选课 |
| `mixed_mode` | 是否使用 API 与 DOM 交替的混合模式 |
| `courses` | 目标课程配置 |

## 课程配置

```json
"课程名": {
    "course_code": "课程代码",
    "label": "标签词",
    "class_id": "教学班号关键词",
    "teacher": "教师关键词"
}
```

匹配规则：

- `course_code` 用于区分同名课程。
- `label` 匹配教学班标签，例如运动项目或课程方向。
- `class_id` 匹配教学班号。
- `teacher` 匹配教师姓名。
- `label`、`class_id`、`teacher` 都为空时，会尝试选择第一个可用教学班。

## 运行模式

| 模式 | 配置 | 说明 |
|---|---|---|
| 纯 DOM | `api_mode=false`, `mixed_mode=false` | 通过页面点击完成选课 |
| 纯 API | `api_mode=true` | 登录后通过浏览器上下文直接请求接口 |
| 混合模式 | `mixed_mode=true` | API 与 DOM 交替执行，兼顾速度与兜底 |

混合模式下只会开启一个窗口，避免同一账号同时操作同一页面造成冲突。

## 常见问题

**多账号会互相顶号吗？**

不会。每个账号使用独立的 `chrome_data/账号` 数据目录，Cookie、localStorage 和登录态互相隔离。

**浏览器窗口为什么会保留？**

脚本退出时只断开 WebDriver 连接，不主动关闭 Chrome 窗口，方便查看页面状态。

**ChromeDriver 出错怎么办？**

重新运行：

```bash
python updateDriver.py
```

如果仍然失败，请检查 Chrome 是否已安装，或在 `config.json` 中手动填写 `chrome_path`。

## 目录说明

| 文件 | 说明 |
|---|---|
| `main.py` | 主程序 |
| `updateDriver.py` | ChromeDriver 自动下载与更新 |
| `config.example.json` | 配置模板 |
| `setup.bat` / `setup.sh` | 环境初始化脚本 |
| `run_app_in_venv_windows.bat` / `run_app.sh` | 启动脚本 |

## 免责声明

本工具仅供学习交流。请遵守学校系统规则和相关规定，使用后果自行承担。
