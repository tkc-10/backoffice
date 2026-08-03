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

# python3 が存在するか確認
if ! command -v python3 &>/dev/null; then
  echo ""
  echo "[エラー] python3 が見つかりません。"
  echo "         https://www.python.org/ からインストールしてください。"
  read -p "Enterキーで閉じます..."
  exit 1
fi

# 依存パッケージの確認・インストール
echo "[確認] 必要なパッケージを確認しています..."
if ! python3 -c "import fastapi, uvicorn, multipart" &>/dev/null; then
  echo "[インストール] 依存パッケージをインストールします（初回のみ）..."
  python3 -m pip install -r requirements.txt
  if [ $? -ne 0 ]; then
    echo ""
    echo "[エラー] パッケージのインストールに失敗しました。"
    read -p "Enterキーで閉じます..."
    exit 1
  fi
  echo "[OK] インストール完了"
fi

echo ""
echo "[起動] http://127.0.0.1:8000"
echo "       停止するには Ctrl+C を押してください"
echo ""

# ブラウザを自動で開く（サーバー起動後に待ってから）
(sleep 2 && open http://127.0.0.1:8000) &

python3 server.py

# サーバーが終了したらターミナルを開いたままにする
echo ""
echo "サーバーが停止しました。"
read -p "Enterキーで閉じます..."
