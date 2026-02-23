#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# uv 설치 확인
if ! command -v uv &>/dev/null; then
    echo "uv가 설치되어 있지 않습니다. 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 가상환경 존재 여부 확인 → 없으면 생성
if [ ! -d ".venv" ]; then
    echo "가상환경이 없습니다. uv sync로 환경을 생성합니다..."
    uv sync
    echo "환경 셋업 완료."
fi

# 실행
uv run tokyo-travel "$@"
