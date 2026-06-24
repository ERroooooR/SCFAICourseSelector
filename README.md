# SCFAI 自动选课工具

> 四川美术学院智慧教务自动选课 — Python + Selenium，跨平台，国内镜像开箱即用。

## 快速开始

```bash
# 1. 编辑 config.json，填你要选的课和时间
# 2. 双击运行（会自动装依赖 + 下载匹配的 ChromeDriver）

Windows: 双击 run_app_in_venv_windows.bat
Linux:   bash setup.sh && bash run_app.sh
```

浏览器打开登录页 → **手动登录一次** → 等时间到自动抢课。

---

## 工作流程

```
登录 → 直达选课列表 → 等时间到 → 双 Tab 并行抢课
         │
         ├─ Tab1 [轮询]  逐门遍历，全部失败后刷新重来
         └─ Tab2 [激进]  锁定一门死磕，元素存在就不刷新
```

点击课程 → Modal 弹出 → 扫描教学班行 → 跳过时间冲突/满员/锁定 → 匹配标签/班号 → 选择确认

---

## 配置文件 `config.json`

```json
{
    "begin_time": "2025-9-25 13:00:30",
    "delay_time": 0.8,
    "click_burst": 8,
    "dual_mode": true,
    "chrome_path": "",
    "fuzzy_match": true,

    "courses": {
        "体育2": {
            "label": "羽毛球",
            "class_id": "",
            "teacher": ""
        }
    }
}
```

### 配置项说明

| 键 | 类型 | 说明 |
|---|---|---|
| `begin_time` | string | 抢课开始时间，格式 `YYYY-M-D HH:MM:SS` |
| `delay_time` | float | 页面加载等待秒数，网络慢可调大 |
| `click_burst` | int | 单门课一轮最多连击次数（不刷新） |
| `dual_mode` | bool | `true`=双Tab并行(轮询+激进)，`false`=仅轮询 |
| `api_mode` | bool | `true`=API 直连选课（JSON 解析，快 10-100 倍），`false`=DOM 点击 |
| `auto_login` | bool | `true`=启动后自动填写学号密码并登录 |
| `username` | string | 学号（`auto_login=true` 时必填） |
| `password` | string | 密码（`auto_login=true` 时必填） |
| `chrome_path` | string | Chrome 路径，留空自动检测 |
| `fuzzy_match` | bool | `true`=课程名模糊匹配（`"体育"` 可点 `"体育2"`），`false`=精确匹配 |

### 课程配置 `courses`

```json
"课程名": {
    "label": "标签关键词",   // 模糊匹配教学班标签（如"羽毛球"匹配"羽毛球"）
    "class_id": "班号"       // 模糊匹配教学班号（如"026"匹配"[理论]006653-026"）
}
```

- `label`、`class_id`、`teacher` 是 **OR 关系**，任意命中即匹配
- 三者都为空 → 自动选第一个可用班（跳过冲突/满员/锁定）
- 简写：`"体育2": "羽毛球"` 等价于 `{"label": "羽毛球", "class_id": "", "teacher": ""}`

### 自动回退逻辑

Modal 内逐行扫描教学班，遇到以下情况**自动跳过**：

| 跳过条件 | 标识 |
|---------|------|
| 已选 | 最后一列显示 `已选` |
| 容量已满 | 最后一列显示 `容量已满`，如 `45 / 45` |
| 教学班锁定 | `lock` 图标 + `教学班已锁定` |
| 时间冲突 | `exclamation-circle` 感叹号图标 |

跳过第一个 → 自动回退到第二个，直到找到符合条件且无冲突的行。

---

## 手动运行（高级）

```bash
# 单独更新 ChromeDriver
python updateDriver.py

# 启动抢课
python main.py

# 如果缺依赖
pip install selenium requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 文件结构

```
├── main.py            # 主程序
├── updateDriver.py    # ChromeDriver 自动下载（国内镜像优先）
├── config.json        # 配置文件（编辑这个就行）
├── driver/            # ChromeDriver 存放目录
├── setup.bat / .sh    # 环境配置脚本（venv + 依赖 + driver）
├── run_app_*.bat/.sh  # 一键启动脚本
└── README.md
```

---

## 常见问题

**Q: 两个 Tab 只有一个能用？**

A: 两个 Tab 共享同一 Chrome 实例（远程调试端口），只需在任意 Tab 登录一次。如端口 9222 冲突，改 `Properties.REMOTE_DEBUG_PORT`。

**Q: ChromeDriver 版本不匹配？**

A: 脚本会自动检测本地 Chrome 版本并下载匹配的 ChromeDriver，优先走 npmmirror 国内镜像。也可手动 `python updateDriver.py`。

**Q: 找不到 Chrome？**

A: 装到默认路径，或在 `config.json` 中设 `chrome_path` 为你的 Chrome 可执行文件路径。

**Q: Linux 权限错误？**

A: `chmod +x driver/chromedriver`，脚本通常已自动设置。

---

## 免责声明

本工具仅供学习交流，请遵守学校规定。使用后果由使用者自行承担。

MIT License
