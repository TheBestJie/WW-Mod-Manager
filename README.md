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
| 快捷键弹窗 | `R` | 修改选中键位（写回 ini）；小写 `r` 亦可 |
| 任意界面 | `Ctrl+U` | 检查更新（有新版本时可直接更新） |
| 任意列表 | `Esc` | 返回上一级 |

切换 mod 后回到游戏按 `F10` 让 WWMI 重新加载。

`Ctrl+U` 是全局绑定且优先级最高：在设置页、搜索框、快捷键编辑屏等**任何输入框里按下它
都只会弹出检查更新窗口**，不会删除光标到行首的内容。输入框里要删左侧内容见
[关于 `Ctrl+U`](#关于-ctrlu)。

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

只读取 mod 目录下会生效的 ini（跳过 `DISABLED*` 和隐藏目录），查看时不改任何文件。
mod 处于禁用状态时，弹窗会提示这些按键在游戏里不会生效。

### 修改快捷键

在快捷键弹窗里选中一行按 `R`（Shift+R，小写 `r` 亦可）进入编辑屏：

- `Enter` 确认并写回 ini，`Esc` 取消（ini 保持原样）；
- 输入框下方实时显示格式化后的预览，非法写法会把中文错误就地显示出来；
- 写回是原子的（临时文件 + `os.replace`）：只替换目标行，BOM、`;` 注释、空行、
  其他 section 和同段的其他 `key`/`back` 行都原样保留；同段有多条 `key` 时按出现次序
  定位，改第 2 条不会动第 1 条，改 `back` 不会动 `key`；
- 分组标题行（切换/长按/其他）不能编辑。

键位写法必须是 XXMI（3Dmigoto `vkeys.h`）支持的组合，用空格或 `+` 分隔：

```text
ctrl alt f7      → ctrl alt VK_F7
Ctrl+Backspace   → ctrl VK_BACK
ctrl semicolon   → ctrl VK_OEM_1
vk_insert        → VK_INSERT
0x70             → 0x70
XB1_A            → XB1_A
no_ctrl f7       → no_ctrl VK_F7
```

即单个字符（只限字母 `a`–`z` 和数字 `0`–`9`，符号请写 `VK_OEM_1` 这类键名）、`VK_` 名称
（可省略 `VK_` 前缀）、`0x` 十六进制码、`XB_` 手柄键和 `no_` 排除前缀。输入会先归一成
游戏真正认识的 `vkeys.h` 写法再写进 ini（修饰键小写 `ctrl`/`alt`/`shift`/`win`，其余用
`VK_` 常量，字母统一大写，重复写法只留一个），所以 `Backspace`、`SEMICOLON` 这类展示
标签会各自落成 `VK_BACK`、`VK_OEM_1` 而不是原样写进去。中文、乱码 token、空输入、只写
排除项、只写修饰键（`key = ctrl` 在游戏里什么都不触发；真要绑 Windows 键本身请写
`0x5B`/`0x5C`）和 WWMI 不认识的组合会被拒绝并给出中文错误，不会写进 ini。

已有的 mod 里如果写的是 `key = ;` 这种单字符标点，列表里仍能正常显示（见下），但在编辑屏
原样回车会被拒，需要改写成 `VK_OEM_1`（`/`→`VK_OEM_2`、`=`→`VK_OEM_PLUS`、
`'`→`VK_OEM_7`）；单字符只收 `A`–`Z` 与 `0`–`9`。同理，已有 ini 里的 `key = VK_LWIN`
（或 `key = win`）现在也会被拒——纯修饰词在游戏里不触发任何键，要绑 Windows 键本身请改成
`0x5B`/`0x5C`；而 `VK_LSHIFT`/`VK_LCONTROL`/`VK_LMENU` 这类分侧键码本身就是按键，可以单独写。

ini 里 `key = CTRL 0 ; 说明` 这种行尾注释不会被当成按键：解析时只在 `;`/`#` 前有空白时
才截掉注释，所以 `key = ;` 仍然是分号键。写回时目标行原有的行尾注释会保留。

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

## 检查更新与自更新

启动时会在后台静默对比
[GitHub releases](https://github.com/TheBestJie/WW-Mod-Manager/releases) 的最新 tag
与本地版本号：

- 有新版本：主页弹一条通知「发现新版本 vX.Y.Z（当前 v…）· Ctrl+U 立即更新」；
- 已是最新、没有 release、断网、JSON 解析失败：**只写日志（`log.debug`），不弹任何错误、
  不阻塞界面**，读取的接口是 `/releases/latest`，`v` 前缀会去掉后按 `X.Y.Z` 数值比较。

随时按 `Ctrl+U` 手动检查，弹屏会给出结果：

- 已是最新：显示当前版本号，无需操作；
- 有新版本：给出版本对比，点「更新」执行 `git pull --ff-only`；检测到 `uv` 时再执行
  `uv tool install --editable --force <仓库路径>`，完成后需重启 `wwmm` 生效；
- 检查或更新失败：弹屏显示中文错误，并指明失败在哪一步（检查 / `git pull` / uv 重装）；
  自更新只对 git clone + `install.sh` 的 editable 安装生效，找不到仓库根目录时给出手动更新
  地址，不会执行任何 git 命令。

### 关于 `Ctrl+U`

`Ctrl+U` 是应用级全局绑定，并且 `priority=True`：**它在任何输入框里也优先开弹屏**，
所以设置页、搜索框、快捷键编辑屏的输入框里按下它都不会再删掉光标到行首的内容。
这是刻意的取舍——手动检查更新的入口必须随处可用，而输入框里的删除操作都有等价按键：

| 想做的事 | 用这个 |
|---|---|
| 删到上一个词首（连按可清空整行） | `Ctrl+W` |
| 删到行尾 | `Ctrl+K` |
| 一次删到行首 | `Shift+Home` 选中到行首后 `Backspace`，或 `Super+Backspace`（≈ macOS `Cmd+Delete`） |
| 逐字向右删 | `Delete` 或 `Ctrl+D` |
| 移到行首 / 行尾 | `Ctrl+A` / `Ctrl+E` |

`Super+Backspace` 在 Textual 里仍然绑定着 `delete_left_all`，能否触发取决于终端是否把该
组合上报给应用。

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

## 发布

版本号写在两处，必须同步（`tests/test_release_workflow.py::test_version_is_synced_across_sources`
会拦住只改一处的情况）：

- `pyproject.toml` 的 `project.version`：`perform_self_update` 用它判断更新后的版本；
- `src/wwmm/__init__.py` 的 `__version__`：`wwmm --version` 和更新检查展示的版本。

升级版本：改这两处 → 提交 → 打 tag 并推送（`tests/test_cli.py` 里还有一处 `--version`
断言和 `uv.lock` 的包版本会跟着变，跑一次 `uv sync` 加 `pytest` 就知道有没有漏）：

```bash
git tag v1.3.0
git push origin main --tags
```

`.github/workflows/release.yml` 会在 `v*` tag 推送时用 `gh release create` 建同名 release
（`--generate-notes` 自动生成 release notes）。启动检查读的就是这个 release，**没有
release 时自更新功能等于不存在**，所以发版必须打 tag。

workflow 在发布前会核对 `v$GITHUB_REF_NAME` 与 `pyproject.toml` 的 `project.version`：
不一致就直接失败。这一步防的是「tag 打了 v1.4.0 但版本号还停在 1.3.0」——那样更新完成后
界面会同时显示「已更新到 v1.3.0」和「最新 v1.4.0」，用户会陷入反复点更新的循环。

## 开发

```bash
pytest
ruff check .
ruff format --check .
```

测试全部使用临时目录，不会触碰真实 Mods 路径。
