# SCFAI 自动选课工具

> 四川美术学院智慧教务自动选课 — Python + Selenium，跨平台，国内镜像开箱即用。

## 快速开始

```bash
# 1. 复制 config.example.json 为 config.json，填好课程和时间
# 2. 双击运行

Windows: 双击 run_app_in_venv_windows.bat
Linux:   bash setup.sh && bash run_app.sh
```

首次运行自动安装依赖 + 下载匹配的 ChromeDriver，无需手动配置。

---

## 三种运行模式

| 模式 | `api_mode` | `mixed_mode` | 轮询 Tab | 激进 Tab |
|------|-----------|-------------|----------|----------|
| 纯 DOM | `false` | `false` | DOM 点击 | DOM 点击 |
| 纯 API | `true` | — | API 直连 | API 直连 |
| **混合** | `false` | `true` | DOM 点击 | API 直连 |

### DOM 模式

模拟浏览器点击：点击课程 → Modal 弹窗 → 遍历教学班 → checkbox → 确认 → 确认

- 最稳定，适合所有课型
- 每轮约 0.5~2 秒

### API 模式

直接调用学校 API：GET 课程列表 → GET 教学班详情 → JSON 过滤匹配 → POST 提交选课

- 比 DOM 快 10-100 倍，每轮约 0.05~0.2 秒
- 纯 JSON 解析，不依赖 DOM 结构
- 内置限速保护：≥1s 间隔 + 遇限速指数退避
- GET 不限速，POST 限速（每次提交最小间隔 1s）

### 混合模式

轮询用 DOM 保底兜底，激进用 API 极速锁课，互补最优。

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
    "mixed_mode": true,
    "auto_login": true,
    "username": "你的学号",
    "password": "你的密码",
    "chrome_path": "",

    "courses": {
        "精彩周1": {
            "course_code": "130508027",
            "label": "",
            "class_id": "",
            "teacher": "程玮楠"
        }
    }
}
```

### 配置项说明

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `begin_time` | string | — | 抢课开始时间 `YYYY-M-D HH:MM:SS` |
| `delay_time` | float | `0.8` | 页面加载等待秒数 |
| `click_burst` | int | `8` | 单门课一轮最大连击次数（仅 DOM 模式） |
| `fuzzy_match` | bool | `true` | 课程名模糊匹配 |
| `dual_mode` | bool | `true` | 双 Tab 并行 |
| `api_mode` | bool | `false` | 双 Tab 都用 API |
| `mixed_mode` | bool | `false` | 混合模式：轮询 DOM + 激进 API |
| `auto_login` | bool | `false` | 自动填充学号密码登录 |
| `username` | string | `""` | 学号 |
| `password` | string | `""` | 密码 |
| `chrome_path` | string | `""` | Chrome 路径，留空自动检测 |

### 课程配置 `courses`

```json
"课程名": {
    "course_code": "课程代码",  // 可选。同名不同码时必填，模糊匹配 codeR
    "label":       "标签词",    // 模糊匹配教学班标签
    "class_id":    "班号词",    // 模糊匹配班号
    "teacher":     "教师词"     // 模糊匹配教师名
}
```

- `course_code` — 课程级过滤，区分同名不同码的课程。未填则只按课程名匹配
- `label` / `class_id` / `teacher` — 教学班级匹配，OR 关系，任意命中即可
- 四个字段全空 → 自动选第一个可用班
- 简写：`"体育2": "羽毛球"` 等价于 `{"course_code": "", "label": "羽毛球", "class_id": "", "teacher": ""}`

### 自动跳过条件

| 条件 | API 判断 | DOM 判断 |
|------|---------|---------|
| 已选 | `selectedFlag === true` | 单元格 `已选` |
| 容量满 | `selectedNum >= stuCapacity` | 单元格 `容量已满` |
| 锁定 | `selectCourseLocked === true` | lock 图标 |
| 时间冲突 | `errorList.length > 0` | 感叹号图标 |

---

## 双 Tab 并行

```
Tab1 [轮询]  逐门遍历所有课程 → 全部失败 → 刷新 → 再来
Tab2 [激进]  锁定一门死磕，元素存在就不刷新，连点到底
```

两 Tab 共享同一 Chrome 实例（远程调试端口 9222），只登录一次。

---

## FAQ

**Q: 同名课程怎么选？**

A: 填 `course_code`。例如 5 个"精彩周1"不同代码，配置 `"course_code": "130508027"` 精确命中。

**Q: API 模式报 401？**

A: 确认浏览器已登录且当前在选课列表页。Token 从 `localStorage.cqu_edu_ACCESS_TOKEN` 读取。

**Q: ChromeDriver 版本不匹配？**

A: 自动检测 Chrome 版本并下载匹配驱动，优先 npmmirror 镜像。

**Q: 找不到 Chrome？**

A: 装默认路径，或 `config.json` 设 `chrome_path`。

---

## 手动运行

```bash
python updateDriver.py                                          # 更新驱动
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python main.py
```

---

## 文件结构

```
├── main.py                   # 主程序
├── updateDriver.py           # ChromeDriver 自动下载
├── config.example.json       # 配置文件模板
├── requirements.txt          # Python 依赖
├── setup.bat / setup.sh      # 环境配置
├── run_app_*.bat / run_app.sh # 一键启动
└── README.md
```

---

## 免责声明

本工具仅供学习交流。使用后果自行承担。MIT License。
