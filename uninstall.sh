#!/usr/bin/env bash
# Uninstall wwmm and remove the PATH blocks written by install.sh.
set -euo pipefail

MARK_START="# >>> wwmm installer >>>"
MARK_END="# <<< wwmm installer <<<"

usage() {
    cat <<'EOF'
用法: ./uninstall.sh [选项]

  --keep-shell-config  只卸载 wwmm，不修改 bash/zsh/fish 的 PATH 配置
  -h, --help           显示这份帮助

脚本会卸载 uv tool 里的 wwmm，并移除 install.sh 写入的 PATH 配置块。
不会删除你的配置、角色表、日志或 Mods 目录。
EOF
}

KEEP_SHELL_CONFIG=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --keep-shell-config)
            KEEP_SHELL_CONFIG=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "错误: 未知参数 $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if [ -z "${HOME:-}" ]; then
    echo "错误: HOME 未设置，无法确定用户配置目录" >&2
    exit 1
fi

remove_block() {
    local file="$1"
    local tmp
    if [ ! -f "$file" ]; then
        return 0
    fi
    if ! grep -qF -- "$MARK_START" "$file"; then
        return 0
    fi
    tmp=$(mktemp)
    awk -v start="$MARK_START" -v end="$MARK_END" '
        $0 == start { skip = 1; next }
        $0 == end { skip = 0; next }
        !skip { print }
    ' "$file" > "$tmp"
    cat "$tmp" > "$file"
    rm -f -- "$tmp"
}

CONFIG_FAILED=0
if [ "$KEEP_SHELL_CONFIG" -eq 0 ]; then
    echo "==> 移除 bash / zsh / fish 的 PATH 配置..."
    remove_block "$HOME/.bashrc" || CONFIG_FAILED=1
    remove_block "${ZDOTDIR:-$HOME}/.zshrc" || CONFIG_FAILED=1
    remove_block "${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish" || CONFIG_FAILED=1
    if [ "$CONFIG_FAILED" -ne 0 ]; then
        echo "警告: 部分 shell 配置清理失败，请手动删除带 wwmm installer 标记的块。" >&2
    fi
else
    echo "==> 保留 shell 配置（--keep-shell-config）"
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "错误: 没有找到 uv，无法卸载 uv tool。" >&2
    echo "PATH 配置已清理；如仍存在 wwmm，请手动删除对应的可执行文件。" >&2
    exit 1
fi

if uv tool list 2>/dev/null | grep -q '^ww-mod-manager\([[:space:]]\|$\)'; then
    echo "==> 卸载 wwmm..."
    uv tool uninstall ww-mod-manager
else
    echo "==> wwmm 未通过 uv tool 安装，跳过工具卸载"
fi

if command -v wwmm >/dev/null 2>&1; then
    echo "提示: 当前 shell 的 PATH 里仍能看到 wwmm: $(command -v wwmm)" >&2
    echo "      可能来自其他虚拟环境或安装位置。" >&2
fi

CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

cat <<EOF

卸载完成。以下用户数据仍然保留:
  配置:   $CONFIG_HOME/wwmm/config.toml
  角色表: $DATA_HOME/wwmm/roster.json
  日志:   $STATE_HOME/wwmm/wwmm.log

重新打开终端后 wwmm 命令会消失。
EOF
