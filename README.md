# SCFAI 自动选课工具

> 四川美术学院智慧教务自动选课 — Python + Selenium，跨平台，支持多账号并发 + 代理池。

## 快速开始

```bash
# 1. 复制 config.example.json 为 config.json
# 2. 编辑 config.json，填入账号和课程
# 3. 双击运行

Windows: 双击 run_app_in_venv_windows.bat
Linux:   bash setup.sh && bash run_app.sh
```

## 多账号 vs 单账号

| 格式 | 说明 |
|------|------|
| 新格式 `global + accounts[]` | 多账号并发（推荐） |
| 旧格式（直接 key） | 单账号，自动转为 `accounts[1]` |

每个账号独立 Chrome 进程 + 独立 `--user-data-dir`，cookie/localStorage/登录态天然隔离，互不顶号。

## 三种运行模式

| 模式 | `api_mode` | `mixed_mode` | 轮询 Tab | 激进 Tab |
|------|-----------|-------------|----------|----------|
| 纯 DOM | `false` | `false` | DOM 点击 | DOM 点击 |
| 纯 API | `true` | — | API 直连 | API 直连 |
| **混合** | `false` | `true` | DOM 点击 | API 直连 |

### 混合模式（推荐）

轮询用 DOM 保底兜底，激进用 API 极速锁课，互补最优。

---

## 代理池

```json
"proxies": [
    "http://proxy1:8080",
    "socks5://proxy2:1080"
]
```

留空数组 `[]` 则直连。每个账号轮询分配一个代理。支持 HTTP/HTTPS/SOCKS5。

---

## 配置文件 `config.json`

```json
{
    "global": {
        "begin_time": "2025-9-25 13:00:30",
        "delay_time": 0.8,
        "click_burst": 8,
        "chrome_path": "",
        "fuzzy_match": true
    },
    "proxies": [],
    "accounts": [
        {
            "name": "张三",
            "username": "2025211656",
            "password": "密码",
            "auto_login": true,
            "dual_mode": true,
            "api_mode": false,
            "mixed_mode": true,
            "courses": {
                "精彩周1": {
                    "course_code": "130508027",
                    "label": "",
                    "class_id": "",
                    "teacher": "程玮楠"
                }
            }
        },
        {
            "name": "李四",
            "username": "2025211888",
            "password": "密码",
            "auto_login": true,
            "dual_mode": false,
            "api_mode": true,
            "mixed_mode": false,
            "courses": {
                "体育2": { "label": "篮球" }
            }
        }
    ]
}
```

### 全局配置

| 键 | 默认 | 说明 |
|---|---|---|
| `begin_time` | — | 抢课开始时间 |
| `delay_time` | `0.8` | 页面加载等待秒 |
| `click_burst` | `8` | 单门课一轮最大连击（DOM） |
| `fuzzy_match` | `true` | 课程名模糊匹配 |
| `chrome_path` | `""` | Chrome 路径，留空自动检测 |
| `proxies` | `[]` | 代理池，每个账号轮询一个 |

### 账号配置

| 键 | 默认 | 说明 |
|---|---|---|
| `name` | — | 标识名 |
| `username` | `""` | 学号 |
| `password` | `""` | 密码 |
| `auto_login` | `false` | 自动填充登录 |
| `dual_mode` | `true` | 双 Tab 并行 |
| `api_mode` | `false` | 全 API |
| `mixed_mode` | `false` | 混合模式 |
| `courses` | — | 课程配置 |

### 课程配置

```json
"课程名": {
    "course_code": "课程代码",
    "label":       "标签词",
    "class_id":    "班号词",
    "teacher":     "教师词"
}
```

四个字段全空 → 自动选第一个可用班。`course_code` 区分同名不同码课程。

---

## FAQ

**Q: 多账号会被顶号吗？**

A: 不会。每个账号独立 Chrome 进程 + 独立 `--user-data-dir`，全程隔离。

**Q: 代理池怎么配？**

A: `"proxies": ["http://ip:port", "socks5://ip:port"]`。留空直连。每个账号轮询分配一个。

**Q: Cookie 过期？**

A: `auto_login=true` 时自动重登。首次登录后 Cookie 持久化到 `chrome_data/` 目录。

---

## 免责声明

本工具仅供学习交流。使用后果自行承担。MIT License。
