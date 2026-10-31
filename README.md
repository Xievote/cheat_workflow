# GTV · 单机游戏修改器管理器（Game Trainer Vault）

用 Python + PySide6 写的 Windows 桌面应用：把你散落在各处的**单机游戏修改器（Trainer）**整理成一个可搜索、可分类、可收藏、可一键启停的本地库。

---

## ⚠️ 使用声明（务必先读）

1. **本工具仅适用于单机 / 离线游戏**，用于本地存档娱乐、无障碍辅助或降低重复劳动。
2. **严禁**在任何联机模式、多人服务器、排行榜、竞技环境中使用修改器；含联机模式的游戏（如 GTA V、荒野大镖客 2）在库中会打上明显的橙色警示标签，并在启动时二次确认。
3. 本程序**不制作、不修改、不注入**任何游戏进程，也不具备绕过反作弊（EAC / BattlEye / Vanguard 等）、DRM 或版权保护的能力；它只是一个「索引 + 启动器 + 笔记」。
4. 内置目录为**元数据索引**（游戏名、分类、标签、常见功能清单），**不含任何程序本体**。程序本体请自行前往修改器作者官网获取后导入。
5. Trainer 的工作方式（读写进程内存）天然容易被安全软件**误报**：请自行核验来源、先用杀软扫描，风险自负。

---

## 功能总览

| 模块 | 能力 |
|---|---|
| 内置目录 | 预置 **51 条** flingtrainer.com 常见单机游戏修改器索引（名称/分类/标签/常见功能/官方页面跳转） |
| 导入方式 | ① 本地 exe/压缩包 ② 本地文件夹 ③ 下载直链 ④ 目录扫描批量导入 ⑤ 手动录入元数据 |
| 浏览检索 | 卡片式网格、关键词搜索（游戏名/标题/标签/分类/作者）、多种排序、按侧栏过滤（收藏/已安装/待导入/分类/标签） |
| 管理界面 | 选中条目后右侧展示：运行会话实时状态（PID、运行时长、停止）、热键功能表（可双击编辑、批量粘贴导入）、备注自动保存、最近启动记录 |
| 记录（历史） | 每次启动写库：开始时间、PID、时长、退出码、状态；支持按时间范围筛选、导出 CSV、清理旧记录 |
| 其它 | 收藏、分类/标签自定义、系统托盘、单实例保护、浅色 QSS 主题、SQLite 持久化 |

---

## 为什么用 Python + PySide6，而不是 PHP / Tkinter

* **PHP**：没有成熟的桌面 GUI 生态（PHP Desktop / WinBinder 已基本停更），打包分发困难，Windows 原生能力（托盘、提权、进程、Shell 集成）都要手写扩展，不适合。
* **Tkinter**：控件老旧、高分屏缩放差、缺少样式系统；本项目的卡片网格、可编辑表格、渐变封面等自定义控件成本极高。
* **PySide6（Qt 6 / LGPL）**：原生 Widgets、QSS 主题、`QSystemTrayIcon`、进程管理、SQLite 全都有，**单文件操作少、`subprocess` + `sqlite3` 都是标准能力**，还能用 PyInstaller 打成单个 exe。

---

## 项目结构

```
wb_cheat/
├── gtv/
│   ├── main.py                  # 入口：环境初始化、单实例保护、种子导入、主窗口
│   ├── core/                    # 与 UI 无关的业务内核
│   │   ├── config.py            # 路径/常量/免责声明/目录初始化
│   │   ├── models.py            # Trainer / Option / LaunchRecord / Session 数据模型
│   │   ├── database.py          # SQLite DAO：库、记录、设置、搜索/统计
│   │   ├── catalog.py           # 内置目录加载（seed JSON → 条目），生成官网搜索链接
│   │   ├── importer.py          # 本地导入 / 解密解压 / URL 下载 / 入库
│   │   ├── launcher.py          # 进程启动（含提权）、轮询监控、停止、记录写库
│   │   ├── scanner.py           # 目录扫描，推断游戏名、去重
│   │   └── utils.py             # 文件名清洗、相似度、体积格式化等
│   └── ui/
│       ├── theme.py             # 浅色 QSS 主题与调色板
│       ├── widgets.py           # FlowLayout 流式布局、封面绘制、Chip、对话框工具
│       ├── main_window.py       # 三栏主窗口：工具栏 / 侧栏导航 / 网格 / 托盘
│       ├── trainer_card.py      # 修改器卡片（封面、状态、收藏、运行按钮、右键菜单）
│       ├── detail_panel.py      # 详情 + 会话管理界面（本次核心联动）
│       ├── add_dialog.py        # 添加修改器（5 个 Tab）
│       └── dialogs.py           # 编辑 / 启动记录 / 设置 / 关于
├── data/
│   └── trainers_seed.json       # 内置修改器元数据（51 条）
├── tools/
│   └── build_exe.py             # PyInstaller 打包脚本
├── assets/                      # 预留：图标等资源
├── run.bat                      # Windows 双击启动
├── requirements.txt
└── README.md
```

**用户数据目录**（不随仓库分发，自动创建）：
`%APPDATA%\GameTrainerVault\`
```
library.db      SQLite 主库
trainers\       修改器本体（每个游戏一个子目录）
downloads\      URL 下载暂存
covers\         封面缓存
logs\gtv.log    崩溃日志
```

---

## 核心模块设计

### 1. 数据模型（SQLite 单库，两张主表 + 一张 KV 设置表）

```
trainers (修改器条目)
  id, title, game_title, category, tags(JSON), version, author,
  source(builtin|local|url), source_url, exe_path, work_dir, args,
  run_as_admin, cover_color, cover_path, options(JSON), notes,
  online_risk, favorite, run_count, last_run_at, created_at, updated_at

launch_records (启动记录)
  id, trainer_id(FK), pid, started_at, ended_at, duration_sec,
  exit_code, status(running|finished|failed|killed), message

settings (key, value)
  archive_passwords / default_admin / minimize_to_tray / confirm_online / first_run_done
```

`options` 以 JSON 存放 `[{key:"Num 1", desc:"无限生命", note:""}]`，便于详情表格直接增删改。

### 2. 数据流

```
                 ┌──────────── data/trainers_seed.json（元数据索引）─────┐
                 │                        │                            │
              首次启动                 catalog.load_seed()          seed_meta()
                 │                        │                            │
                 ▼                        ▼                            ▼
  ┌────────────────────────── Database(SQLite) ◄────────── upsert_seed_item（去重）
  │                              ▲        │
  │   importer.materialize() ────┘        │  search(keyword, side, sort)
  │   (本地/文件夹/URL → 入库 + 找主 exe)     ▼
  │                                  MainWindow
  │  scanner.scan(dir) → 候选列表 ──►  FlowLayout + TrainerCard（网格）
  │                                        │ 选中 / 启动 / 收藏
  │                                        ▼
  │                                  DetailPanel（详情 + 会话管理）
  │                                        │
  └────────────────── Launcher ────────────┤  Popen / ShellExecute(runas)
              subprocess 起进程 ──► QTimer 1.5s 轮询 exit code
                                           ▼
                                    launch_records 写库
```

### 3. 导入器（`core/importer.py`）

优先级策略：**文件夹 > 压缩包 > 单 exe**。入库时统一复制到 `%APPDATA%\GameTrainerVault\trainers\<游戏名>\`，
避免原文件被删除/移动导致条目失效；复制后在目录内用打分函数挑主程序：

```
score = 文件名含 "fling" +5，含 "trainer" +3，含 cheat/+版本号 +1
       命中 unins/setup/install/crack/keygen/readme 等关键词 → 直接淘汰 (score = -1)
按 (score, 体积MB) 降序取第一个作为主 exe
```

### 4. 启动器（`core/launcher.py`）

* 普通启动：`subprocess.Popen`，拿到 PID，`QTimer` 每 1.5s `poll()`，退出即写 `launch_records`（含退出码与时长）。
* 管理员启动：Windows `ShellExecuteW(..., "runas")`，可提权但**拿不到 PID**，因此记录一条即时完成的历史，避免"永久 running"脏数据。
* 退出应用前会提示并尝试 `stop_all()`，防止 Trainer 变孤儿进程。
* 会话对象内存态维护 `trainer_id → Session(pid, start_time, proc)`，UI 通过信号 `sessionStarted / sessionEnded` 更新卡片按钮与详情面板。

### 5. 安全设计

| 威胁 | 处置 |
|---|---|
| 压缩包路径穿越（Zip-Slip） | 每个成员解析后必须落在解压根目录内，否则整包拒绝；成员数 > 2000 拒绝 |
| 解压炸弹 | 单成员压缩比 > 400 且体积 > 200MB 拒绝 |
| 加密压缩包 | 候选密码（可在设置里维护）逐个试读；失败则明确报错而非静默 |
| 下载风险 | 仅 http/https，扩展名白名单 `.zip/.7z/.rar/.exe`，体积上限 300MB，超时 60s |
| 进程卫生 | 停止用 `taskkill /PID /T /F`（Windows），清理子进程树 |
| SQL 注入 | 全部参数化查询 |

---

## 运行方式

### 一键（Windows 双击）

```bat
run.bat
```
脚本会自动创建虚拟环境、安装依赖并启动（首次较慢）。

### 手动

```bash
pip install -r requirements.txt
python -m gtv.main
```

### 打包成 exe

```bash
pip install pyinstaller
python tools/build_exe.py
# 产出：dist/GTV.exe
```

---

## 常见用法

1. **先装本体再跑**：内置目录里的条目默认是「未导入」状态（灰色圆点）。点击条目 → 弹窗提示未安装 →「+ 添加修改器」→ 选择本地文件或<｜hy_place▁holder▁no▁813｜>下载直链即可补齐。也可以在「添加」对话框里选「关联到已有条目」。
2. **热键表**：详情页的功能表格支持双击改热键、批量粘贴（每行 `Num 1  无限生命`）、一键复制到剪贴板 —— 从官网说明页 Ctrl+C 过来直接粘即可。
3. **每次都卡住的那一项**：写进「备注」区，自动保存。
4. **含联机模式的游戏**：卡片与详情会显示橙色警示条，启动前需二次确认（可在设置中关闭确认，但不建议）。

---

## 路线图（可选扩展）

* [ ] 远程封面/元信息拉取（SteamGridDB 等），需用户自填 API Key
* [ ] 备份/导出整个库为 zip（含本体目录），便于换机
* [ ] 每条记录的"热键速查"浮窗（置顶小窗，游戏中随时查看）
* [ ] 标签云 + 自动分类聚类
* [ ] 便携模式（把 SQLite 与 trainers 目录放在程序目录下）

---

## 依赖

```
PySide6-Essentials>=6.8
PyInstaller>=6.0     # 仅打包时需要
```

标准库：`sqlite3 / zipfile / subprocess / urllib / ctypes / json / pathlib`。
7z / rar 解压依赖本机已安装 **7-Zip**（推荐）或 WinRAR；zip 为标准库原生支持。
