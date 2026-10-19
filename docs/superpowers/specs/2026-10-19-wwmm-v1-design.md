# WWMM V1 设计：Linux 原生鸣潮 Mod 管理器

- 日期：2026-10-19
- 状态：已与用户确认
- 关联计划：`docs/superpowers/plans/2026-10-19-wwmm-v1.md`

## 1. 背景与目标

用户从 Windows 迁移到 Arch Linux。鸣潮通过 Wine/Proton 运行，Windows 版 XXMI Launcher + WWMI 在 Wine 下正常工作，但 JASM 等 Windows 管理器无法在 Wine 下安装。需要一个**原生运行在 Linux 上**的 TUI 工具，直接操作 Wine 前缀里的 Mods 目录，完成按属性分类、搜索、启停 mod 的工作。

成功标准：打开终端输入 `wwmm`，能在三级界面里快速找到某个角色的 mod 并开关；启动时自动补全角色目录；角色表可由 GitHub Actions 每日自动更新。

## 2. 范围

### V1 包含

1. 设置并持久化 WWMI 的 Mods 目录。
2. 扫描 `Mods/character/<角色>/<mod>`，正确处理任意深度的 mod 内部嵌套。
3. 按六属性（冷凝、热熔、导电、气动、衍射、湮灭）+ 多属性/其他/未分类分组。
4. 三级选项式界面：属性 → 角色 → mod。
5. 全局搜索：中文、英文、拼音、首字母、属性别名，直接跳到角色 mod 列表。
6. 启用/禁用：只重命名 mod 顶层文件夹的 `DISABLED_` 前缀。
7. 启动时自动创建角色表里缺失的 `character/<slug>` 空目录。
8. `wwmm update`：拉取角色表、校验、写入本地、补目录。
9. GitHub Actions 每日从 Arikatsu 解包数据生成 `data/roster.json` 并提交。

### V1 不包含

- 图形界面（V2 再考虑）。
- 安装、解压、下载、删除 mod。
- 启动游戏或发送 F10；切换后只提示用户回游戏按 F10。
- 多选批量开关、mod 冲突检测、撤销、文件监听、mod 预览图。
- Windows 原生运行（代码尽量跨平台，但只验收 Linux）。

## 3. 已确认的运行事实

- 游戏运行方式：Wine/Proton；XXMI 是 Windows 版，装在 Wine 前缀里。
- 用户当前 Mods 目录：
  `/home/lujie/.proton/pfx/drive_c/Program Files/XXMI Launcher/WWMI/Mods`
- `WWMI/d3dx.ini` 中：
  - `include_recursive = Mods`
  - `exclude_recursive = DISABLED*`
- 因此禁用 = 给 mod 顶层文件夹加 `DISABLED_` 前缀；不需要移出 Mods，也不需要改 ini。
- 当前结构：`Mods/character/<角色>/<mod>/...`；18 个角色目录、62 个 mod（41 禁用、21 启用），最深 5 层，没有压缩包。
- 一个 mod 的原子单位 = `character/<角色>` 的**直接子文件夹**；其内部 `Weapon/Sword/mod.ini`、多套 `mod.ini` 都视为同一个 mod 的组成部分。
- 角色表（3.7）：60 个英文名，其中漂泊者 4 个形态合并为 1 个 → 57 个基础角色 + `others`。用户现有 17 个角色目录，启动补全会新增 40 个角色目录 + 确保 `others`，共 58 个目录。
- 关键映射修正：`lucilla` = **洛瑟菈（Lucilla，冷凝）**；`lucy` = **露西（Lucy，衍射）**，是另一个角色。`rover` = 漂泊者（多属性），`others` = 其他。

## 4. 目录与开关语义

```
Mods/
└── character/
    ├── aemeath/
    │   ├── Aemeath - Sky Pixie/
    │   │   ├── mod.ini
    │   │   └── Weapon/Sword/mod.ini
    │   └── DISABLED_Aemeath - Old/
    ├── denia/
    │   └── 达妮娅-红绳捆绑/
    └── others/
```

- 角色目录名 = 角色表里的 `folder`（默认等于 `slug`），大小写不敏感匹配；不重命名已有角色目录。
- mod 目录名去掉 `DISABLED_` 后是展示名；`enabled = not name.startswith("DISABLED_")`。
- 开关只 `os.rename` 这一层；目标已存在、权限不足、名字过长时中止并报错，绝不删除或覆盖。
- 内部嵌套的 `DISABLED` 子目录不受影响（它们属于 mod 自身）。
- 非 mod 的松散文件、压缩包：V1 忽略，不展示、不操作。

## 5. 数据模型

### Roster JSON（schema v1）

```json
{
  "schema_version": 1,
  "game_version": "3.7",
  "source": {
    "repo": "Arikatsu/WutheringWaves_Data",
    "branch": "3.7",
    "commit": "…",
    "committed_at": "2026-10-18T…Z"
  },
  "characters": [
    {
      "slug": "denia",
      "name_zh": "达妮娅",
      "name_en": "Denia",
      "elements": ["热熔"],
      "pinyin": "daniya",
      "initials": "dny",
      "aliases": ["达妮娅", "denia", "daniya"],
      "folder": "denia",
      "special": false
    },
    {
      "slug": "rover",
      "name_zh": "漂泊者",
      "name_en": "Rover",
      "elements": ["衍射", "湮灭", "气动", "导电"],
      "pinyin": "piaobozhe",
      "initials": "pbz",
      "aliases": ["漂泊者·衍射", "漂泊者·湮灭", "漂泊者·气动", "漂泊者·导电"],
      "folder": "rover",
      "special": false
    },
    {
      "slug": "others",
      "name_zh": "其他",
      "name_en": "Others",
      "elements": [],
      "pinyin": "qita",
      "initials": "qt",
      "aliases": ["其他", "others"],
      "folder": "others",
      "special": true
    }
  ]
}
```

- `group` 由 `elements` 计算：单属性 → 属性名；多属性 → “多属性”；空且 special → “其他”；未知目录 → “未分类”。
- 分组顺序固定：冷凝、热熔、导电、气动、衍射、湮灭、多属性、其他、未分类。
- `pinyin`/`initials` 由中文名生成；`aliases` 包含社区常用别名。
- 角色表来源优先级：本地 `~/.local/share/wwmm/roster.json` > 包内置 `src/wwmm/data/roster.json`。

### 运行时模型

- `Character`：角色元数据 + `group`。
- `Mod`：`path`、`folder_name`、`enabled`、`ini_count`。
- `CharacterEntry`：`character`、`path`、`mods`、`enabled_count`、`total_count`、`has_mods`。
- `Snapshot`：`mods_root`、按固定分组顺序的 `groups: dict[str, list[CharacterEntry]]`、`scanned_at`。

## 6. UI

### 主页（属性选择）

```text
┌ 主页 ─────────────────────────────────────┐
│  › 冷凝     3/9 角色  ·  8 mods           │
│    热熔     4/11 角色 · 18 mods           │
│    导电     2/10 角色 · 14 mods           │
│    气动     2/10 角色 ·  8 mods           │
│    衍射     2/8 角色  ·  3 mods           │
│    湮灭     3/8 角色  ·  7 mods           │
│    多属性   1/1 角色  ·  2 mods           │
│    其他     1/1 角色  ·  2 mods           │
├───────────────────────────────────────────┤
│ ↑↓ 选择  Enter 进入  / 搜索  s 设置  u 更新  q 退出 │
└───────────────────────────────────────────┘
```

- `x/y 角色`：x = 有 mod 的角色数，y = 该属性下角色总数（含空目录）。
- mod 数 = 该属性下所有 mod 总数（含禁用）。
- “未分类”仅在有未知目录时出现。

### 角色列表

- 显示 `中文名 (slug)  启用/总数`；空角色淡显。
- `h` 隐藏/显示空角色；`/` 聚焦过滤框；Enter 进入 mod 列表；Esc 返回。
- 默认按“有 mod 优先，再按中文名”排序。

### mod 列表

- 显示 `● 启用` / `○ 禁用`、展示名、ini 数量；0 ini 标黄警告。
- 底部详情：完整文件夹名、路径、ini 数、当前状态。
- `Space` 开关当前项；`/` 过滤；`r` 刷新；Esc 返回。
- 切换成功后 toast：“已启用 X · 回游戏按 F10”；失败显示错误，不改文件。
- 返回上级时重新扫描，计数自动更新。

### 搜索

- 主页按 `/` 打开全局搜索（Modal）。
- 支持中文、英文、slug、拼音、首字母（如 `dn` → 达妮娅）、属性别名（雷/电磁 → 导电，火 → 热熔，冰 → 冷凝，风 → 气动，光 → 衍射，暗 → 湮灭）。
- Enter 直接进入该角色的 mod 列表，不必逐级点击；Esc 关闭。
- 角色列表和 mod 列表里的 `/` 是当前列表的过滤，不跨级。

### 设置

- 首次启动或 Mods 路径无效时进入设置页。
- 自动探测常见路径：`~/.proton`、`~/.wine`、Steam `compatdata/*/pfx` 下的 `XXMI Launcher/WWMI/Mods`。
- 校验：目录存在；`<path>/character` 存在，或目录名为 `Mods`，或父目录有 `d3dx.ini`。否则拒绝保存，避免在错误目录创建 58 个文件夹。
- 保存后立即补目录并扫描。

### 更新

- 主页 `u` → 确认 → 拉取角色表 → 校验 → 写本地 → 补目录 → 刷新计数。
- 更新只加不删：角色从表里消失时，旧文件夹保留并归“未分类”。

## 7. 角色表流水线

### GitHub Actions

- `.github/workflows/update-roster.yml`
- 每天 03:00（北京时间，UTC `0 19 * * *`）运行；支持 `workflow_dispatch`。
- 先查 Arikatsu 默认分支和 HEAD；如果 `data/roster.json` 的 `source.commit` 相同，直接退出，不下载 100MB。
- 有变化才下载：
  - `BinData/role/roleinfo.json`
  - `Textmaps/zh-Hans/multi_text/MultiText.json`
  - `Textmaps/en/multi_text/MultiText.json`
- 解析：`RoleType=1` 且 `QualityId in (4,5)`；`ElementId` 1..6 映射六属性；漂泊者形态合并；追加 `others`。
- 生成 slug/中英文名/属性/拼音/首字母/别名；边界情况读 `scripts/roster_overrides.json`。
- 校验：角色数 ≥ 50、slug 唯一、六属性齐全、`rover` 和 `others` 存在；失败退出，不覆盖旧文件。
- 原子写入 `data/roster.json`；内容没变不提交。
- 提交信息：`chore(roster): sync <game_version>`。

### app 侧

- `wwmm update` 默认拉：
  `https://raw.githubusercontent.com/TheBestJie/WW-Mod-Manager/main/data/roster.json`
- 支持 `--from FILE`（离线）、`--dry-run`、`--force`、`--no-create`、`--url`。
- 写入 `~/.local/share/wwmm/roster.json`，旧文件备份为 `roster.json.bak`。
- 远程 `source.committed_at` 比本地旧时拒绝降级，除非 `--force`。
- 拉取失败保留本地版本并报错。

### 仓库前提

- raw 地址要求仓库公开；私有仓库用 `--from` 或配置镜像 URL。
- 分支保护要允许 Actions push。
- 仓库连续 60 天无活动，定时任务会被 GitHub 停用；游戏每个版本更新角色表通常会保持活跃，真停了手动 `workflow_dispatch`。

## 8. 技术栈与路径

- Python ≥ 3.11；开发环境 Python 3.14；Actions 用 3.12。
- Textual 8.x（当前 8.2.8）、platformdirs、tomli-w、pypinyin。
- 测试：pytest、pytest-asyncio、PyYAML（只用于校验 workflow YAML）。
- 包管理：`uv`（已安装）；`uv venv .venv`、`uv pip install -e ".[dev]"`。
- 配置：`~/.config/wwmm/config.toml`
- 本地角色表：`~/.local/share/wwmm/roster.json`
- 日志：`~/.local/state/wwmm/wwmm.log`
- 包内置角色表：`src/wwmm/data/roster.json`
- 规范角色表：`data/roster.json`

## 9. 安全与失败处理

- 只重命名顶层 mod 文件夹；不删除、不移动、不改内部文件。
- 目标已存在 → 中止；权限/名字过长 → 中文错误提示；失败时文件系统保持原状。
- 所有单元测试和 UI 测试只用临时目录，绝不指向真实 Mods 路径。
- 设置页严格校验 Mods 目录，避免误建 58 个目录。
- 更新前校验新角色表；失败不覆盖本地；写入使用临时文件 + `os.replace`。
- 日志记录启动、扫描计数、创建的目录、每次开关、更新结果和错误。
- 更新只加目录，从不删除角色目录。

## 10. 验收标准

1. `wwmm` 在 Arch Linux 终端启动；无配置时进入设置页。
2. 设置真实 Mods 路径后，启动补全 40 个缺失角色目录，并显示 58 个目录的统计。
3. 主页按属性分组，计数与真实目录一致（62 mods）。
4. 属性 → 角色 → mod 三级导航可用；Esc 逐级返回。
5. `/` 输入 `dn` 能直接进入达妮娅的 mod 列表。
6. 对临时目录里的 mod 按 Space，文件夹在 `X` 与 `DISABLED_X` 之间切换；真实目录测试只在临时副本进行。
7. `wwmm update --from data/roster.json --dry-run` 不写文件；不带 dry-run 时写本地并补目录。
8. `pytest` 全绿；`ruff check .` 无错误。
9. GitHub Actions 在数据无变化时跳过下载；有变化时提交 `data/roster.json`。
