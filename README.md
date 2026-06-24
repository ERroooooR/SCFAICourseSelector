# SCFAI 自动选课工具

> 四川美术学院智慧教务自动选课 — Python + Selenium，跨平台，国内镜像开箱即用。

## 快速开始

```bash
# 1. 编辑 config.json，填好课程和时间
# 2. 双击运行

Windows: 双击 run_app_in_venv_windows.bat
Linux:   bash setup.sh && bash run_app.sh
```

首次运行自动安装依赖 + 下载匹配的 ChromeDriver，无需手动配置。

---

## 两种模式

### DOM 模式（`api_mode: false`）

模拟浏览器点击：点击课程 → Modal 弹窗 → 遍历教学班 → checkbox → 确认 → 确认

- 适合所有情况，稳定可靠
- 每轮约 0.5~2 秒（受 Modal 渲染和页面刷新影响）

### API 模式（`api_mode: true`）

直接调用学校 API：GET 课程列表 → GET 教学班详情 → JSON 过滤匹配 → POST 提交选课

- 比 DOM 快 10-100 倍，每轮约 0.05~0.2 秒
- 纯 JSON 解析，不依赖 DOM 结构
- 需浏览器登录一次（提取 token），后续全部走 API
- 内置限速保护：两次提交间隔 ≥1s，遇限速自动指数退避

---

## 配置文件 `config.json`

```json
{
    "begin_time": "2025-9-25 13:00:30",
    "delay_time": 0.8,
    "click_burst": 8,
    "fuzzy_match": true,
    "dual_mode": true,
    "api_mode": false,
    "auto_login": false,
    "username": "",
    "password": "",
    "chrome_path": "",

    "courses": {
        "体育2": {
            "label": "羽毛球",
            "class_id": "",
            "teacher": "纪超香"
        }
    }
}
```

### 配置项说明

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `begin_time` | string | — | 抢课开始时间 `YYYY-M-D HH:MM:SS` |
| `delay_time` | float | `0.8` | 页面加载等待秒数 |
| `click_burst` | int | `8` | 单门课一轮最大连击次数（不刷新） |
| `fuzzy_match` | bool | `true` | 课程名模糊匹配，`"体育"` 可命中 `"体育2"` |
| `dual_mode` | bool | `true` | 双 Tab 并行（轮询 + 激进） |
| `api_mode` | bool | `false` | API 直连选课，比 DOM 快 10-100x |
| `auto_login` | bool | `false` | 自动填充学号密码并登录 |
| `username` | string | `""` | 学号 |
| `password` | string | `""` | 密码 |
| `chrome_path` | string | `""` | Chrome 路径，留空自动检测 |

### 课程配置 `courses`

```json
"课程名": {
    "label":    "标签关键词",   // 模糊匹配教学班标签，如 "羽毛球" 匹配 "羽毛球"
    "class_id": "班号词",       // 模糊匹配班号，如 "026" 匹配 "[理论]006653-026"
    "teacher":  "教师词"        // 模糊匹配教师名，如 "纪超" 匹配 "纪超香"
}
```

- `label` / `class_id` / `teacher` **OR 关系**，任意一项命中即匹配
- 三者全空 → 自动选第一个可用班
- 简写：`"体育2": "羽毛球"` 等价于 `{"label": "羽毛球", "class_id": "", "teacher": ""}`

### 自动跳过条件

| 条件 | API 模式判断 | DOM 模式判断 |
|------|-------------|-------------|
| 已选 | `selectedFlag === true` | 单元格显示 `已选` |
| 容量已满 | `selectedNum >= stuCapacity` | 单元格显示 `容量已满` |
| 锁定 | `selectCourseLocked === true` | lock 图标 |
| 时间冲突 | `errorList.length > 0` | exclamation-circle 图标 |

---

## 双 Tab 并行

```
Tab1 [轮询]  逐门遍历所有课程 → 全部失败 → 刷新 → 再来
Tab2 [激进]  锁定一门死磕，元素存在就不刷新，连点到底
```

两 Tab 共享同一 Chrome 实例（远程调试端口 9222），登录一次即可。

---

## 文件结构

```
├── main.py                    # 主程序
├── updateDriver.py            # ChromeDriver 自动下载（国内镜像优先）
├── config.json                # 配置文件（编辑这个即可）
├── requirements.txt           # Python 依赖
├── driver/                    # ChromeDriver 存放目录
├── setup.bat / setup.sh       # 环境配置（venv + 依赖 + driver）
├── run_app_in_venv_windows.bat   # Windows 一键启动
├── run_app.sh                 # Linux 一键启动
└── README.md
```

---

## 手动运行

```bash
# 更新 ChromeDriver
python updateDriver.py

# 安装依赖（国内清华镜像）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 启动
python main.py
```

---

## 常见问题

**Q: API 模式报 401？**

A: 确认浏览器已登录、当前在 `CourseStuSelectionList` 页面。Token 从 `localStorage.cqu_edu_ACCESS_TOKEN` 读取，只在登录后存在。

**Q: 两个 Tab 只有一个能用？**

A: 在任意 Tab 登录一次即可。如端口 9222 冲突，改 `Properties.REMOTE_DEBUG_PORT`。

**Q: ChromeDriver 版本不匹配？**

A: 脚本自动检测 Chrome 版本并下载匹配的驱动，优先 npmmirror 镜像。手动 `python updateDriver.py`。

**Q: 找不到 Chrome？**

A: 装默认路径，或在 `config.json` 设 `chrome_path`。

**Q: Linux 权限错误？**

A: `chmod +x driver/chromedriver`，脚本通常自动设置。

---

## 免责声明

本工具仅供学习交流，请遵守学校规定。使用后果由使用者自行承担。

MIT License
