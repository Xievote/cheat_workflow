# GTV · 单机游戏修改器管理与内存修改平台

用 Python + PySide6 写的 Windows 桌面应用，两部分能力合在一个界面里：

1. **修改器库**：把你散落在各处的单机游戏修改器（Trainer）整理成可搜索、可分类、可收藏、可一键启停的本地库；
2. **内存修改**：在 Cheat Engine 里查到数值地址后录入平台，平台自动为每条数值生成交互控件（滑动条 / 数值框 / 按钮 / 开关），拖动即实时读写游戏内存，并每 0.5 秒回读当前值确认生效。

---

## ⚠️ 使用声明（务必先读）

1. **本工具仅适用于单机 / 离线游戏**，用于本地存档娱乐、无障碍辅助或降低重复劳动。
2. **严禁**在任何联机模式、多人服务器、排行榜、竞技环境中使用；含联机模式的游戏（如 GTA V、荒野大镖客 2）在库中会打上明显的橙色警示标签，并在启动时二次确认。
3. 本程序**不注入 DLL**、不修改游戏文件、不具备绕过反作弊（EAC / BattlEye / Vanguard 等）、DRM 或版权保护的能力。但它会通过 Windows 原生 API（`OpenProcess` / `ReadProcessMemory` / `WriteProcessMemory`，由 `pymem` 封装）**直接读写你手动指定的目标进程内存**——这是「内存修改」功能的必要实现，请在你自己拥有的游戏上使用。
4. 内置目录为**元数据索引**（游戏名、分类、标签、常见功能清单），**不含任何程序本体**。程序本体请自行前往修改器作者官网获取后导入。
5. Trainer 与内存读写工具天然容易被安全软件**误报**：请自行核验来源、先用杀软扫描，风险自负。

---

## 功能总览

| 模块 | 能力 |
|---|---|
| 内置目录 | 预置 **51 条** flingtrainer.com 常见单机游戏修改器索引（名称/分类/标签/常见功能/官方页面跳转） |
| 导入方式 | ① 本地 exe/压缩包 ② 本地文件夹 ③ 下载直链 ④ 目录扫描批量导入 ⑤ 手动录入元数据 |
| 库列表 | **纵向条形卡片**：迷你封面 + 游戏名 + 分类/标签/作者副标题 + 地址数徽标 + 导入状态 + 运行次数 + 收藏 + 启动按钮；支持关键词搜索、排序、侧栏过滤（收藏/已安装/待导入/分类/标签） |
| 游戏详情页 | 点击条形卡片进入：启动/停止、附加进程、新增地址；左侧内存地址列表，右侧热键表 + 备注 + 最近启动记录 |
| 内存修改 | 每条地址一行 = 数值名称 + **实时读取值**（0.5 秒轮询）+ **修改方式下拉（滑动条/数值框/按钮/开关，随时切换并持久化）** + 对应控件，操作即写入内存 |
| 地址管理 | 支持绝对地址与「模块+偏移」两种写法、指针偏移链（与 CE 规则一致）、6 种数据类型；增删改、启用/停用、排序 |
| 记录（历史） | 每次启动写库：开始时间、PID、时长、退出码、状态；支持按时间范围筛选、导出 CSV、清理旧记录 |
| 其它 | 收藏、分类/标签自定义、系统托盘、单实例保护、浅色 QSS 主题、SQLite 持久化 |

界面预览（离屏渲染）：`docs/preview_library.png`（库列表）、`docs/preview_detail.png`（游戏详情页）。

---

## 为什么用 Python + PySide6，而不是 PHP / Tkinter

* **PHP**：没有成熟的桌面 GUI 生态（PHP Desktop / WinBinder 已基本停更），打包分发困难，Windows 原生能力（托盘、提权、进程、内存 API、Shell 集成）都要手写扩展，不适合。
* **Tkinter**：控件老旧、高分屏缩放差、缺少样式系统；本项目的条形卡片、可编辑表格、渐变封面、自定义滑动条等控件成本极高。
* **PySide6（Qt 6 / LGPL）**：原生 Widgets、QSS 主题、`QSystemTrayIcon`、进程管理、SQLite 全都有，还能用 PyInstaller 打成单个 exe。
* **pymem**：进程附加、模块基址枚举、按类型读写内存都已封装好（底层仍是 ctypes 调 Win32 API），省掉约 300 行样板代码；对 64 位进程与指针链解析支持完善。

---

## 项目结构

```
cheat_workflow/
├── gtv/
│   ├── main.py                  # 入口：环境初始化、单实例保护、种子导入、主窗口
│   ├── boot.py                  # 无控制台启动入口（pythonw -m gtv.boot）
│   ├── core/                    # 与 UI 无关的业务内核
│   │   ├── config.py            # 路径/常量/免责声明/目录初始化
│   │   ├── models.py            # Trainer / Option / MemoryEntry / LaunchRecord / Session
│   │   ├── database.py          # SQLite DAO：库、内存地址、记录、设置、搜索/统计
│   │   ├── catalog.py           # 内置目录加载（seed JSON → 条目），生成官网搜索链接
│   │   ├── importer.py          # 本地导入 / 解密解压 / URL 下载 / 入库
│   │   ├── launcher.py          # 进程启动（含提权）、轮询监控、停止、记录写库
│   │   ├── memory_engine.py     # pymem 封装：附加/分离、基址解析、指针链、按类型读写
│   │   ├── scanner.py           # 目录扫描，推断游戏名、去重
│   │   └── utils.py             # 文件名清洗、相似度、体积格式化等
│   └── ui/
│       ├── theme.py             # 浅色 QSS 主题与调色板（含蓝底 Tooltip）
│       ├── widgets.py           # 封面绘制、Chip、分隔线、对话框工具
│       ├── main_window.py       # 主窗口：工具栏 / 侧栏导航 / QStackedWidget（列表页 + 详情页）/ 托盘
│       ├── trainer_row.py       # 纵向条形卡片（封面、名称、副标题、地址数、状态、收藏、启动）
│       ├── game_detail.py       # 游戏详情页：启动/附加、内存地址列表与控件、热键/备注/记录
│       ├── memory_dialog.py     # 内存地址录入/编辑对话框（地址校验、偏移链解析）
│       ├── add_dialog.py        # 添加修改器（5 个 Tab）
│       └── dialogs.py           # 编辑 / 启动记录 / 设置 / 关于
├── data/
│   └── trainers_seed.json       # 内置修改器元数据（51 条）
├── docs/                        # 界面预览截图
├── tools/
│   ├── build_exe.py             # PyInstaller 打包脚本
│   ├── test_memory_engine.py    # 内存引擎全链路自测（自附加）
│   ├── test_memory_ui.py        # UI 冒烟测试（临时库，离屏）
│   └── shot_ui.py               # 离屏渲染界面截图
├── GTV.vbs                      # 双击无黑窗启动
├── run.bat                      # 依赖检查 + 启动
├── requirements.txt
└── README.md
```

**用户数据目录**（不随仓库分发，自动创建）：
`%APPDATA%\GameTrainerVault\`
```
library.db      SQLite 主库（含 memory_entries 表）
trainers\       修改器本体（每个游戏一个子目录）
downloads\      URL 下载暂存
covers\         封面缓存
logs\gtv.log    崩溃日志
```

---

## 核心模块设计

### 1. 数据模型（SQLite 单库，三张主表 + 一张 KV 设置表）

```
trainers (游戏/修改器条目)
  id, title, game_title, category, tags(JSON), version, author,
  source(builtin|local|url), source_url, exe_path, work_dir, args,
  run_as_admin, cover_color, cover_path, options(JSON), notes,
  online_risk, favorite, run_count, last_run_at, created_at, updated_at

memory_entries (内存地址配置，外键 → trainers，ON DELETE CASCADE)
  id, trainer_id, name, addr, offsets(JSON), dtype, control,
  value, minv, maxv, step, note, enabled, sort, created_at, updated_at

launch_records (启动记录)
  id, trainer_id(FK), pid, started_at, ended_at, duration_sec,
  exit_code, status(running|finished|failed|killed), message

settings (key, value)
  archive_passwords / default_admin / minimize_to_tray / confirm_online / first_run_done
```

* `options` 以 JSON 存放 `[{key:"Num 1", desc:"无限生命", note:""}]`，便于详情表格直接增删改。
* `memory_entries` 的 `offsets` 以十六进制字符串数组存放（如 `["0x10","0x4"]`），删除游戏时**级联清理**，不留脏配置。

### 2. 内存地址的写法与解析

| 字段 | 说明 |
|---|---|
| `addr` | **绝对地址** `7FF6A1B2C3D0`（或 `0x...`）/ **模块+偏移** `game.exe+1A2B3C`（推荐，游戏重启后依然有效） |
| `offsets` | 指针偏移链，如 `0x10 → 0x4`；留空表示直接读 `addr` |
| `dtype` | `int32 / int64 / int16 / byte / float / double` |
| `control` | `滑动条 / 数值框 / 按钮 / 开关` |
| `value` | 按钮点击时写入的值；开关开启时写入该值，关闭固定写 `0` |
| `minv / maxv / step` | 滑动条与数值框的范围和步长 |

解析规则与 Cheat Engine 完全一致：

```
基地址 = 模块基址 + 模块偏移（或绝对地址本身）
若 offsets 非空：  指针 = ReadPointer(基地址)
                  最终地址 = 指针 + offsets[0]
                  再逐级：指针 = ReadPointer(最终地址) → + offsets[1] …
```

### 3. 内存引擎（`core/memory_engine.py`）

| 能力 | 说明 |
|---|---|
| 附加 | `attach_pid(pid)` / `attach_name(进程名)`；成功后发出 `attached(pid, name)` 信号，失败返回原因字符串 |
| 分离 | `detach(reason)` 关闭句柄；目标进程退出时由轮询自动触发并通知界面 |
| 基址解析 | 按模块名（不区分大小写）在目标进程模块列表中查基址，支持 `game.exe+1A2B3C` |
| 指针链 | 逐级解引用，任一级读取失败即报「偏移链失效」 |
| 读写 | `read(entry)` / `write(entry, value)`，内部按 `dtype` 走对应的 pymem 方法，异常统一捕获为 `(False, 原因)` |
| 存活检测 | `alive()` 判断 PID 是否还存在，供 500ms 轮询使用 |

界面层每 0.5 秒回读一次所有启用条目：读成功 → 中间格显示新值（写入后短暂高亮）；读失败 → 显示红色错误态并提示分离。

### 4. 界面结构

```
MainWindow
├── 顶部工具栏：搜索 / 排序 / 扫描目录 / + 添加修改器
├── 左侧导航：全部 / 收藏 / 已安装 / 待导入 / 分类 / 标签
├── 中央 QStackedWidget
│   ├── 页1 库列表：纵向条形卡片（TrainerRow）滚动列表
│   │      └─ 点击 → 切到页2
│   └── 页2 游戏详情页（GameDetailPage）
│          ├─ 返回按钮 + 封面 + 名称 + 分类标签 + 收藏/编辑/官网/目录/删除
│          ├─ 操作条：启动·停止 ｜ 附加进程·选择进程·分离 ｜ + 新增地址
│          ├─ 状态条：运行会话（PID / 时长）+ 附加状态
│          ├─ 左：内存地址列表（EntryRow × N，实时值 + 修改方式下拉 + 控件）
│          └─ 右：功能热键表 / 备注 / 最近启动记录
└── 状态栏：操作反馈
```

列表页与详情页在同一窗口内切换，**内存修改与条目管理同屏协同**，不需要来回切 Tab。窗口默认 1320×860，左右分栏可拖动调整，适配 1280×800 以上的桌面分辨率。

### 5. 数据流

```
                 ┌──────────── data/trainers_seed.json（元数据索引）─────┐
                 │                        │                            │
              首次启动                 catalog.load_seed()          seed_meta()
                 │                        │                            │
                 ▼                        ▼                            ▼
  ┌────────────────────────── Database(SQLite) ◄────────── upsert_seed_item（去重）
  │                        ▲        │
  │  importer.materialize()│        │  search(keyword, side, sort)
  │  (本地/文件夹/URL → 入库)│        ▼
  │                        │   MainWindow.lib_page（条形卡片列表）
  │  scanner.scan(dir) ────┘         │ 点击卡片 select_trainer()
  │                                  ▼
  │                          GameDetailPage
  │                            │  ├─ Launcher ──► Popen / ShellExecute(runas)
  │                            │  │               QTimer 1.5s 轮询 exit code → launch_records
  │                            │  ├─ MemoryEngine ──► pymem 附加 / resolve / read / write
  │                            │  │                   QTimer 500ms 回读 → EntryRow 数值格
  │                            │  └─ memory_entries CRUD（增删改 + 修改方式切换）
  └────────────────────────────────┘
```

### 6. 导入器（`core/importer.py`）

优先级策略：**文件夹 > 压缩包 > 单 exe**。入库时统一复制到 `%APPDATA%\GameTrainerVault\trainers\<游戏名>\`，
避免原文件被删除/移动导致条目失效；复制后在目录内用打分函数挑主程序：

```
score = 文件名含 "fling" +5，含 "trainer" +3，含 cheat/+版本号 +1
       命中 unins/setup/install/crack/keygen/readme 等关键词 → 直接淘汰 (score = -1)
按 (score, 体积MB) 降序取第一个作为主 exe
```

### 7. 启动器（`core/launcher.py`）

* 普通启动：`subprocess.Popen`，拿到 PID，`QTimer` 每 1.5s `poll()`，退出即写 `launch_records`（含退出码与时长）。
* 管理员启动：Windows `ShellExecuteW(..., "runas")`，可提权但**拿不到 PID**，因此记录一条即时完成的历史，避免"永久 running"脏数据。
* 退出应用前会提示并尝试 `stop_all()`，防止 Trainer 变孤儿进程。
* 会话对象内存态维护 `trainer_id → Session(pid, start_time, proc)`，UI 通过信号 `sessionStarted / sessionEnded` 更新卡片按钮与详情页状态。
* **与内存引擎的联动**：启动游戏后 500ms 自动按该条目的 exe 名尝试附加；游戏退出 → 自动分离；切换游戏 → 先分离再加载，防止把 A 游戏的地址写进 B 进程。

### 8. 安全设计

| 威胁 | 处置 |
|---|---|
| 压缩包路径穿越（Zip-Slip） | 每个成员解析后必须落在解压根目录内，否则整包拒绝；成员数 > 2000 拒绝 |
| 解压炸弹 | 单成员压缩比 > 400 且体积 > 200MB 拒绝 |
| 加密压缩包 | 候选密码（可在设置里维护）逐个试读；失败则明确报错而非静默 |
| 下载风险 | 仅 http/https，扩展名白名单 `.zip/.7z/.rar/.exe`，体积上限 300MB，超时 60s |
| 进程卫生 | 停止用 `taskkill /PID /T /F`（Windows），清理子进程树 |
| 内存误写 | 分离/切换游戏时立刻停止读写；地址失效、进程退出统一捕获并提示，不静默写坏数据 |
| SQL 注入 | 全部参数化查询 |

---

## 运行方式

程序以 **`pythonw.exe`** 启动（Windows GUI 子系统，没有控制台窗口），因此：

- 双击 `GTV.vbs` —— **推荐**，全程无任何黑窗口，最适合日常使用
- 双击 `run.bat` —— 负责检查/安装依赖，然后启动 GTV 并**自动关闭自己**（约 2 秒）
- 命令行：`pythonw -m gtv.boot`（无控制台）或 `python -m gtv.boot`（带控制台，用于排错）

> 为什么要这样：以前版本用 `python -m gtv.main` **阻塞式**运行，GUI 挂在控制台进程树上，
> 关掉黑窗会把 GTV 一起带走。现在 GTV 由 pythonw 启动，是**独立进程**，
> 控制台窗口关不关都不影响它。

排错入口：

| 现象 | 处理 |
|---|---|
| 双击后没有任何窗口 | 先看 `%APPDATA%\GameTrainerVault\logs\gtv.log`；运行时错误会同时弹出原生提示框 |
| vbs 被安全软件拦截 | 改用 `run.bat`，或用命令行 `pythonw -m gtv.boot` |
| 想看实时报错输出 | 用 `python -m gtv.boot`（保留控制台） |

### 第一次使用

```bat
run.bat          :: 双击即可，自动建 .venv 并安装依赖（含 pymem，仅首次较慢）
```

### 打包成 exe

```bash
pip install pyinstaller
python tools/build_exe.py
# 产出：dist/GTV/GTV.exe
# 注意：打包后请直接双击 GTV.exe，它本身就是 GUI 程序，无需 bat/vbs
```

---

## 内存修改完整流程

### 第一步：在 Cheat Engine 里找地址

1. CE 附加到游戏进程，首次扫描你要改的数值（例：金币 1234，类型 `4 Bytes`）；
2. 在游戏里让数值变化，用「再次扫描」缩小到 1~2 个地址；
3. **推荐**：右键地址 →「找出是什么访问了这个地址」，拿到指令与偏移，再右键 →「生成指针路径」，
   得到类似 `"game.exe"+01A2B3C → 10 → 4` 的形式 —— 这种写法**重启游戏后依然有效**；
4. 记下：基址写法、偏移链、数据类型（CE 里的 `4 Bytes` = int32，`Float` = float，`8 Bytes` = int64）。

### 第二步：在平台里录入

选中游戏 → 进入详情页 → **「+ 新增地址」**：

| 表单项 | 示例 |
|---|---|
| 数值名称 | 金币 |
| 地址 | `game.exe+1A2B3C`（推荐）或 `7FF6A1B2C3D0` |
| 偏移链 | `10, 4`（可留空；支持 `0x10 0x4`、`10 → 4` 等写法） |
| 数据类型 | int32 |
| 修改方式 | 滑动条 |
| 范围/步长 | 0 ~ 999999，步长 100 |
| 写入值（按钮/开关用） | 999999 |

地址栏会实时校验格式，写错立刻提示，不会等到运行时才报错。

### 第三步：附加进程并修改

1. 点「启动游戏」——平台启动后会自动尝试附加；或点「附加进程」按游戏 exe 名自动查找；
2. 找不到（同名的多个进程 / 名字对不上）会弹**进程选择框**，可从列表挑，也可直接输入 PID；
3. 附加成功后状态条显示 `● 已附加：game.exe (PID 12345)`；
4. 每条地址右侧中间格每 0.5 秒刷新**当前内存值**；拖动滑动条 / 改数值 / 点按钮 / 拨开关即刻写入，写入后格子短暂高亮；
5. 修改方式随时可在下拉框里切换（如滑动条 → 数值框），选择会写回数据库，下次打开保持一致。

> **权限提示**：如果游戏以管理员身份运行，GTV 也必须以管理员身份运行，否则能附加但读写会报「拒绝访问（错误 5）」。

### 常见问题

| 现象 | 原因与处理 |
|---|---|
| 附加成功但数值格显示「—」/ 报错 | 地址或偏移链失效（游戏更新、进错存档、模块名写错）；重开 CE 复核地址 |
| 值能读到但写完没变化 | 该地址是「显示副本」，真正数值在别处；用 CE 的「找出是什么改写了这个地址」再定位 |
| 修改后游戏崩溃 | 多半是数据类型不匹配（如把 float 当 int32 写）；核对 CE 里的类型 |
| 重启游戏后地址全部失效 | 用了绝对地址；改用「模块+偏移」或补全指针链 |
| 找不到进程 | 游戏未启动 / 进程名不是 exe 文件名；用「选择进程」手动挑 |

---

## 其它常见用法

1. **先装本体再跑**：内置目录里的条目默认是「未导入」状态（灰色圆点）。点击条目进入详情 → 弹窗提示未安装 →「+ 添加修改器」→ 选择本地文件或下载直链即可补齐。也可以在「添加」对话框里选「关联到已有条目」。
2. **热键表**：详情页右侧的功能表格支持双击改热键、批量粘贴（每行 `Num 1  无限生命`）、一键复制到剪贴板 —— 从官网说明页 Ctrl+C 过来直接粘即可。
3. **备注**：游戏的特殊启动条件、某个地址的注意事项，写进「备注」区，自动保存。
4. **含联机模式的游戏**：卡片与详情会显示橙色警示条，启动前需二次确认（可在设置中关闭确认，但不建议）。

---

## 路线图（可选扩展）

* [ ] 数值冻结 / 锁定（定时重复写入，对抗游戏自身刷新）
* [ ] 导入 Cheat Engine 的 `.CT` 表，批量生成地址条目
* [ ] 指针扫描器（CE 式多级偏移自动搜索）
* [ ] 修改历史与一键撤销（记录每次写入的旧值）
* [ ] 远程封面/元信息拉取（SteamGridDB 等），需用户自填 API Key
* [ ] 备份/导出整个库为 zip（含本体目录与地址配置），便于换机
* [ ] 标签云 + 自动分类聚类
* [ ] 便携模式（把 SQLite 与 trainers 目录放在程序目录下）

---

## 依赖

```
PySide6-Essentials>=6.8
pymem>=1.13            # 内存读写（附加进程 / 模块基址 / 指针链）
PyInstaller>=6.0       # 仅打包时需要
```

标准库：`sqlite3 / zipfile / subprocess / urllib / ctypes / json / pathlib`。
7z / rar 解压依赖本机已安装 **7-Zip**（推荐）或 WinRAR；zip 为标准库原生支持。

---

## 自测脚本

```bash
.venv/Scripts/python.exe tools/test_memory_engine.py   # 内存引擎全链路（附加/基址/指针链/读写/分离）
.venv/Scripts/python.exe tools/test_memory_ui.py       # UI 冒烟（临时库 + 离屏，不污染真实数据）
.venv/Scripts/python.exe tools/shot_ui.py              # 离屏渲染界面截图到 docs/
```

> 说明：`test_memory_engine.py` 采用**附加自身进程**的方式验证全链路（构造已知地址的变量再读写），
> 因此在任何环境下都能跑；真实跨进程读写请用实际游戏验证。
