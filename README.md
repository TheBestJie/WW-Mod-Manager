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

```bash
git clone git@github.com:TheBestJie/WW-Mod-Manager.git
cd WW-Mod-Manager
uv venv .venv
source .venv/bin/activate
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
| mod 列表 | `Space` | 启用/禁用当前 mod |
| mod 列表 | `/` | 过滤 mod |
| mod 列表 | `r` | 刷新 |
| 任意列表 | `Esc` | 返回上一级 |

切换 mod 后回到游戏按 `F10` 让 WWMI 重新加载。

## 启用/禁用语义

- 只重命名 `character/<角色>/` 的**直接子文件夹**，在名字前加/去一个
  `DISABLED_` 前缀。
- 不删除、不移动、不修改 mod 内部任何文件；嵌套的 `DISABLED` 子目录不受影响。
- 目标名字已存在、权限不足或名字过长时中止并报中文错误，文件系统保持原状。

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
