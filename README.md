# WW-Mod-Manager

鸣潮（Wuthering Waves）Linux 原生 TUI mod 管理器。直接操作 Wine/Proton 前缀里
XXMI Launcher 的 WWMI `Mods` 目录，按属性浏览角色、搜索、用 `DISABLED_` 前缀启停
mod。不需要在 Wine 下安装任何 Windows 管理器。

```text
┌ 主页 ─────────────────────────────────────┐
│  ● 冷凝     3/9 角色  ·  8 mods           │
│  ● 热熔     4/11 角色 · 18 mods           │
│  ● 导电     2/10 角色 · 14 mods           │
│  ● 气动     2/10 角色 ·  8 mods           │
│  ● 衍射     2/8 角色  ·  3 mods           │
│  ● 湮灭     3/8 角色  ·  7 mods           │
│  ● 多属性   1/1 角色  ·  2 mods           │
│  ● 其他     1/1 角色  ·  2 mods           │
├───────────────────────────────────────────┤
│ ↑↓ 选择  Enter 进入  / 搜索  s 设置  u 更新  q 退出 │
└───────────────────────────────────────────┘
```

## 依赖

- Linux（验收环境：Arch Linux）
- Wine/Proton 下可正常运行的 XXMI Launcher + WWMI
- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/)（推荐）

## 安装

### 一键安装（推荐）

```bash
git clone git@github.com:TheBestJie/WW-Mod-Manager.git
cd WW-Mod-Manager
./install.sh
```

脚本会：

- 用 `uv tool install --editable` 把 `wwmm` 安装到 `~/.local/bin`；
- 自动为 **bash、zsh、fish** 写入带标记的 PATH 配置块（可重复运行，不会重复添加）；
- 验证 `wwmm --version`。

重新打开终端后直接输入 `wwmm` 即可。如果当前终端还没生效，按脚本提示
`source` 对应 shell 的配置文件。只想安装、不想改 shell 配置时用：

```bash
./install.sh --no-path
```

卸载：

```bash
./uninstall.sh
```

它会移除 `install.sh` 写入的 bash/zsh/fish PATH 配置块并卸载 uv tool，但保留
配置、角色表、日志和 Mods 目录。只想卸载工具、保留 PATH 配置时用
`./uninstall.sh --keep-shell-config`。

### 手动安装（开发）

```bash
git clone git@github.com:TheBestJie/WW-Mod-Manager.git
cd WW-Mod-Manager
uv venv .venv
source .venv/bin/activate        # fish: source .venv/bin/activate.fish
uv pip install -e ".[dev]"
wwmm
```

## 首次运行

第一次启动会进入设置页。可以：

- 自动探测常见路径：`~/.proton`、`~/.wine`、Steam
  `compatdata/*/pfx` 下的 `XXMI Launcher/WWMI/Mods`；
- 或手动输入 Mods 目录。

只有目录存在，且满足 `<path>/character` 存在、目录名为 `Mods`、或父目录有
`d3dx.ini` 之一时才会保存，避免在错误目录里批量创建角色文件夹。保存后会立即
补全角色表里缺失的 `character/<slug>` 空目录并扫描现有 mod。

## 键位

| 位置 | 键 | 作用 |
|---|---|---|
| 主页 | `↑` `↓` | 选择属性分组 |
| 主页 | `Enter` | 进入角色列表 |
| 主页 | `/` | 全局搜索（中文/英文/拼音/首字母/属性别名） |
| 主页 | `s` | 设置 |
| 主页 | `u` | 更新角色表 |
| 主页 | `r` | 重新扫描 |
| 主页 | `q` | 退出 |
| 角色列表 | `Enter` | 进入 mod 列表 |
| 角色列表 | `/` | 过滤角色 |
| 角色列表 | `h` | 隐藏/显示空角色 |
| 角色列表 | `c` | 复制角色文件夹路径 |
| mod 列表 | `Space` | 启用/禁用当前 mod |
| mod 列表 | `m` | 查看该 mod 的 ini 快捷键 |
| mod 列表 | `c` | 复制当前 mod 文件夹路径 |
| mod 列表 | `/` | 过滤 mod |
| mod 列表 | `r` | 刷新 |
| 任意列表 | `Esc` | 返回上一级 |

切换 mod 后回到游戏按 `F10` 让 WWMI 重新加载。

## 启用/禁用语义

- 只重命名 `character/<角色>/` 的**直接子文件夹**，在名字前加/去一个
  `DISABLED_` 前缀。
- 不删除、不移动、不修改 mod 内部任何文件；嵌套的 `DISABLED` 子目录不受影响。
- 目标名字已存在、权限不足或名字过长时中止并报中文错误，文件系统保持原状。

## 复制文件夹路径

角色列表或 mod 列表选中一项按 `c`，会把该项的绝对路径复制到剪贴板。路径不加引号，
禁用 mod 会带上真实的 `DISABLED_` 前缀，复制后直接在文件管理器地址栏粘贴即可进入。

复制同时走两条通道：终端 OSC 52，以及 `wl-copy` / `xclip` / `xsel`（装了任意一个
即可在 Wayland / X11 下工作）。终端不支持 OSC 52 且没有安装上述工具时，复制可能不生效。

## 查看 mod 快捷键

在 mod 列表选中一项按 `m`，弹窗按 ini 里的 `type` 分组列出所有按键：

- **切换**：`type = cycle` 或 `toggle`，按一下换一个状态；
- **长按**：`type = hold`，按住时生效；
- **其他**：没有 `type` 的默认单次键和鼠标键。

同一段落里的多条 `Key`/`Back` 会各占一行；`Back` 行标注「反向」。
WWMI 全局按键（F6/F10/F12 等）在 `Core/WWMI/KeyBindings.ini`，不在 mod 列表里。

只读取 mod 目录下会生效的 ini（跳过 `DISABLED*` 和隐藏目录），不改任何文件。
mod 处于禁用状态时，弹窗会提示这些按键在游戏里不会生效。

## 更新角色表

```bash
wwmm update                     # 从默认 GitHub raw 地址更新
wwmm update --from data/roster.json
wwmm update --from data/roster.json --dry-run
wwmm update --url https://example.com/roster.json
wwmm update --force             # 允许远程版本比本地旧时覆盖
wwmm update --no-create         # 只更新角色表，不补角色目录
```

更新流程：拉取 → 校验 schema/slug/属性/`rover`/`others`（拒绝空表）→ 备份旧文件为
`roster.json.bak` → 原子写入 → 补全缺失角色目录。校验或下载失败时保留旧角色表。

## 数据与日志路径

| 内容 | 路径 |
|---|---|
| 配置 | `~/.config/wwmm/config.toml` |
| 本地角色表 | `~/.local/share/wwmm/roster.json` |
| 日志 | `~/.local/state/wwmm/wwmm.log` |
| 包内置回退角色表 | `src/wwmm/data/roster.json` |
| 仓库规范角色表 | `data/roster.json` |

## 角色表流水线

`.github/workflows/update-roster.yml` 每天北京时间 03:00（UTC `0 19 * * *`）运行，
也支持手动 `workflow_dispatch`：

1. 查询 [Arikatsu/WutheringWaves_Data](https://github.com/Arikatsu/WutheringWaves_Data)
   的默认分支和 HEAD；
2. 若 `data/roster.json` 的 `source.commit` 相同，直接退出，不下载大文件；
3. 有变化才下载 `roleinfo.json` 与中英文 `MultiText.json`，生成并校验角色表；
4. 原子写入 `data/roster.json`，内容无变化不提交，有变化提交
   `chore(roster): sync <game_version>`。

注意事项：

- 默认 raw 地址要求仓库公开；私有仓库请使用 `wwmm update --from FILE` 或配置
  镜像 URL。
- 分支保护需要允许 GitHub Actions push。
- 仓库连续 60 天无活动时定时任务会被 GitHub 停用；游戏版本更新通常会保持活跃，
  真停了在 Actions 页面手动运行一次即可。

## 开发

```bash
pytest
ruff check .
ruff format --check .
```

测试全部使用临时目录，不会触碰真实 Mods 路径。
