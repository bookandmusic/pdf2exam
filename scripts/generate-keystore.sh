#!/bin/bash

# Android Keystore 生成脚本
# 用于生成签名密钥和配置文件

set -e

# 默认配置
KEYSTORE_FILE="pdf2exam.keystore"
KEY_ALIAS="pdf2exam"
VALIDITY_DAYS=9125  # 25年
KEYSTORE_PASSWORD=""
KEY_PASSWORD=""
DNAME="CN=PDF2Exam, OU=Dev, O=PDF2Exam, L=Beijing, ST=Beijing, C=CN"

# 输出目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ANDROID_DIR="$PROJECT_ROOT/src-tauri/gen/android/app"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --keystore-password)
            KEYSTORE_PASSWORD="$2"
            shift 2
            ;;
        --key-password)
            KEY_PASSWORD="$2"
            shift 2
            ;;
        --alias)
            KEY_ALIAS="$2"
            shift 2
            ;;
        --dname)
            DNAME="$2"
            shift 2
            ;;
        --output)
            ANDROID_DIR="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --keystore-password  密钥库密码 (必需)"
            echo "  --key-password       密钥密码 (可选，默认同密钥库密码)"
            echo "  --alias              密钥别名 (默认: pdf2exam)"
            echo "  --dname              证书信息 (默认: CN=PDF2Exam...)"
            echo "  --output             输出目录 (默认: src-tauri/gen/android/app)"
            echo ""
            echo "示例:"
            echo "  $0 --keystore-password mypassword123"
            exit 0
            ;;
        *)
            print_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查必需参数
if [[ -z "$KEYSTORE_PASSWORD" ]]; then
    print_error "缺少密钥库密码，请使用 --keystore-password 参数"
    exit 1
fi

# 如果未设置密钥密码，使用密钥库密码
if [[ -z "$KEY_PASSWORD" ]]; then
    KEY_PASSWORD="$KEYSTORE_PASSWORD"
    print_info "使用密钥库密码作为密钥密码"
fi

# 检查 keytool 是否可用
if ! command -v keytool &> /dev/null; then
    print_error "keytool 未找到，请确保 Java JDK 已安装"
    exit 1
fi

# 创建输出目录
mkdir -p "$ANDROID_DIR"

# 生成 keystore
KEYSTORE_PATH="$ANDROID_DIR/$KEYSTORE_FILE"

print_info "生成 keystore 文件..."
print_info "  路径: $KEYSTORE_PATH"
print_info "  别名: $KEY_ALIAS"
print_info "  有效期: $VALIDITY_DAYS 天"

keytool -genkeypair \
    -v \
    -keystore "$KEYSTORE_PATH" \
    -alias "$KEY_ALIAS" \
    -keyalg RSA \
    -keysize 2048 \
    -validity "$VALIDITY_DAYS" \
    -storepass "$KEYSTORE_PASSWORD" \
    -keypass "$KEY_PASSWORD" \
    -dname "$DNAME"

print_info "Keystore 已生成"

# 创建 key.properties 文件
KEY_PROPERTIES_PATH="$ANDROID_DIR/key.properties"

print_info "创建 key.properties 文件..."

cat > "$KEY_PROPERTIES_PATH" << EOF
storeFile=$KEYSTORE_FILE
storePassword=$KEYSTORE_PASSWORD
keyAlias=$KEY_ALIAS
keyPassword=$KEY_PASSWORD
EOF

print_info "key.properties 已创建: $KEY_PROPERTIES_PATH"

# 输出警告
print_warn "请妥善保管以下文件和密码:"
print_warn "  - $KEYSTORE_PATH"
print_warn "  - $KEY_PROPERTIES_PATH"
print_warn "  - 密钥库密码和密钥密码"

# 输出 GitHub Secrets 设置指南
echo ""
echo "=========================================="
print_info "GitHub Secrets 配置指南"
echo "=========================================="
echo ""
echo "在 GitHub 仓库设置中添加以下 Secrets:"
echo ""
echo "1. ANDROID_KEYSTORE_BASE64"
echo "   运行以下命令生成:"
echo "   base64 -w 0 $KEYSTORE_PATH"
echo ""
echo "2. ANDROID_KEYSTORE_PASSWORD"
echo "   值: $KEYSTORE_PASSWORD"
echo ""
echo "3. ANDROID_KEY_ALIAS"
echo "   值: $KEY_ALIAS"
echo ""
echo "4. ANDROID_KEY_PASSWORD"
echo "   值: $KEY_PASSWORD"
echo ""
echo "=========================================="

print_info "完成！"