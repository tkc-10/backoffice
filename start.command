#!/bin/bash

# このファイルのあるディレクトリへ移動
cd "$(dirname "$0")"

echo "======================================="
echo "  精算データ処理ツール を起動します"
echo "======================================="
echo ""

# 仮想環境があれば有効化（なければシステムPythonを使用）
if [ -d ".venv" ]; then
  source .venv/bin/activate
  echo "[OK] 仮想環境 (.venv) を使用します"
elif [ -d "venv" ]; then
  source venv/bin/activate
  echo "[OK] 仮想環境 (venv) を使用します"
fi

# ブラウザを自動で開く（サーバー起動後1秒待ってから）
(sleep 1.5 && open http://127.0.0.1:8000) &

echo "[起動] http://127.0.0.1:8000"
echo "       停止するには Ctrl+C を押してください"
echo ""

python3 server.py
