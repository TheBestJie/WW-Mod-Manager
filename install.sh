#!/usr/bin/env bash
# Install wwmm for the current user and add the uv tool bin directory to
# bash, zsh and fish PATH configuration.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MARK_START="# >>> wwmm installer >>>"
MARK_END="# <<< wwmm installer <<<"

usage() {
    cat <<'EOF'
用法: ./install.sh [选项]

  --no-path   只安装 wwmm，不修改 bash/zsh/fish 的 PATH 配置
  -h, --help  显示这份帮助

脚本会使用 uv 以 editable 模式安装 wwmm，并把 uv tool 的可执行文件目录
写入 bash、zsh、fish 的配置，使新终端可以直接运行 wwmm。
EOF
}

NO_PATH=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --no-path)
            NO_PATH=1
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

if ! command -v uv >/dev/null 2>&1; then
    cat >&2 <<'EOF'
错误: 没有找到 uv。

请先安装 uv:
  Arch Linux: sudo pacman -S uv
  其他系统:   curl -LsSf https://astral.sh/uv/install.sh | sh

安装 uv 后重新运行 ./install.sh
EOF
    exit 1
fi

echo "==> 使用 uv 安装 wwmm（editable 模式）..."
uv tool install --editable "$SCRIPT_DIR" --force

BIN_DIR=$(uv tool dir --bin)
if [ -z "$BIN_DIR" ]; then
    echo "错误: 无法确定 uv tool 的可执行文件目录" >&2
    exit 1
fi
if [ ! -x "$BIN_DIR/wwmm" ]; then
    echo "错误: 安装后没有找到可执行文件 $BIN_DIR/wwmm" >&2
    exit 1
fi

escape_double() {
    printf '%s' "$1" | sed 's/[\\"$`]/\\&/g'
}

remove_block() {
    local file="$1"
    local tmp
    tmp=$(mktemp)
    awk -v start="$MARK_START" -v end="$MARK_END" '
        $0 == start { skip = 1; next }
        $0 == end { skip = 0; next }
        !skip { print }
    ' "$file" > "$tmp"
    cat "$tmp" > "$file"
    rm -f -- "$tmp"
}

add_posix_block() {
    local file="$1"
    local escaped
    mkdir -p -- "$(dirname -- "$file")"
    touch -- "$file"
    remove_block "$file"
    escaped=$(escape_double "$BIN_DIR")
    {
        printf '\n%s\n' "$MARK_START"
        printf '%s\n' "# Added by install.sh; remove this block to stop adding wwmm to PATH."
        printf '%s\n' 'case ":$PATH:" in'
        printf '    *":%s:"*) ;;\n' "$escaped"
        printf '    *) export PATH="%s:$PATH" ;;\n' "$escaped"
        printf '%s\n' 'esac'
        printf '%s\n' "$MARK_END"
    } >> "$file"
}

add_fish_block() {
    local file="$1"
    local escaped
    mkdir -p -- "$(dirname -- "$file")"
    touch -- "$file"
    remove_block "$file"
    escaped=$(escape_double "$BIN_DIR")
    {
        printf '\n%s\n' "$MARK_START"
        printf '%s\n' "# Added by install.sh; remove this block to stop adding wwmm to PATH."
        printf 'if not contains -- "%s" $PATH\n' "$escaped"
        printf '    set -gx PATH "%s" $PATH\n' "$escaped"
        printf '%s\n' "end"
        printf '%s\n' "$MARK_END"
    } >> "$file"
}

CONFIG_FAILED=0
if [ "$NO_PATH" -eq 0 ]; then
    echo "==> 配置 bash / zsh / fish 的 PATH..."
    BASH_RC="$HOME/.bashrc"
    ZSH_RC="${ZDOTDIR:-$HOME}/.zshrc"
    FISH_RC="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"

    add_posix_block "$BASH_RC" || CONFIG_FAILED=1
    add_posix_block "$ZSH_RC" || CONFIG_FAILED=1
    add_fish_block "$FISH_RC" || CONFIG_FAILED=1

    if [ "$CONFIG_FAILED" -ne 0 ]; then
        echo "警告: 部分 shell 配置写入失败，请手动把下面这行加入 PATH:" >&2
        echo "  export PATH=\"$BIN_DIR:\$PATH\"" >&2
    fi
else
    echo "==> 跳过 shell 配置（--no-path）"
fi

echo "==> 验证安装..."
"$BIN_DIR/wwmm" --version

cat <<EOF

安装完成: $BIN_DIR/wwmm

如果当前终端还找不到 wwmm，请重新打开终端，或执行:
  bash: source ~/.bashrc
  zsh:  source ${ZDOTDIR:-$HOME}/.zshrc
  fish: source ${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish

卸载: uv tool uninstall ww-mod-manager
EOF

if [ "$NO_PATH" -ne 0 ]; then
    echo
    echo "你使用了 --no-path，需要自己确保该目录在 PATH 中:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
fi
