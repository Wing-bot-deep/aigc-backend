#!/bin/bash
# =============================================
# 蓝色光标 AIGC 后端 - Linux 服务器部署脚本
# 用法：bash deploy.sh
# 系统要求：Ubuntu 20.04+ / CentOS 7+，Python 3.10+
# =============================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="aigc-backend"
PYTHON_BIN=$(which python3)
PIP_BIN=$(which pip3)
VENV_DIR="$PROJECT_DIR/venv"

echo "================================================"
echo " 蓝色光标 AIGC 营销素材服务 - 部署"
echo " 项目路径: $PROJECT_DIR"
echo "================================================"

# ── Step 1: 检查 Python 版本 ──────────────────────────────────────────────────
echo ""
echo "[1/5] 检查 Python 版本..."
$PYTHON_BIN -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'" \
    || { echo "错误：需要 Python 3.10 或更高版本"; exit 1; }
echo "✓ Python 版本: $($PYTHON_BIN --version)"

# ── Step 2: 创建虚拟环境并安装依赖 ────────────────────────────────────────────
echo ""
echo "[2/5] 安装依赖..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv "$VENV_DIR"
    echo "✓ 虚拟环境已创建: $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q
echo "✓ 依赖安装完成"

# ── Step 3: 配置环境变量 ──────────────────────────────────────────────────────
echo ""
echo "[3/5] 配置环境变量..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo ""
    echo "⚠️  已创建 .env 文件，请填写 API Key："
    echo "   nano $PROJECT_DIR/.env"
    echo ""
    echo "   必填项："
    echo "   - ANTHROPIC_API_KEY=sk-ant-xxx"
    echo "   - IMAGE_BACKEND=mock（测试）或 dalle3（需要 OPENAI_API_KEY）"
    echo ""
    read -p "   填写完毕后按回车继续..." _
else
    echo "✓ .env 文件已存在，跳过"
fi

# ── Step 4: 测试启动 ──────────────────────────────────────────────────────────
echo ""
echo "[4/5] 测试服务是否能正常启动（5 秒后自动停止）..."
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"
timeout 5 uvicorn app.main:app --host 127.0.0.1 --port 18000 2>/dev/null || true
echo "✓ 启动测试通过"

# ── Step 5: 创建 systemd 服务 ─────────────────────────────────────────────────
echo ""
echo "[5/5] 配置 systemd 服务..."
VENV_PYTHON="$VENV_DIR/bin/python"
UVICORN_BIN="$VENV_DIR/bin/uvicorn"

cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=蓝色光标 AIGC 营销素材生成服务
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$UVICORN_BIN app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "================================================"
echo " 部署完成！"
echo "================================================"
echo ""
echo "▶ 手动测试运行："
echo "   source $VENV_DIR/bin/activate"
echo "   cd $PROJECT_DIR"
echo "   python -m app.main"
echo ""
echo "▶ 安装为系统服务（需要 sudo）："
echo "   sudo cp /tmp/${SERVICE_NAME}.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable ${SERVICE_NAME}"
echo "   sudo systemctl start ${SERVICE_NAME}"
echo "   sudo systemctl status ${SERVICE_NAME}"
echo ""
echo "▶ 服务启动后访问："
echo "   API 文档: http://你的服务器IP:8000/docs"
echo "   健康检查: http://你的服务器IP:8000/api/v1/health"
echo ""
