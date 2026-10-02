#!/bin/bash

# ============================================================================
# EasyNAS 一键部署脚本
# ============================================================================

set -e

# 获取脚本所在目录作为源码目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="easynas"

# 数据目录默认安装到 /opt/easynas（与源码目录分离）
DEFAULT_DATA_DIR="/opt/easynas/data"
DEFAULT_DOWNLOADS_DIR="/opt/easynas/downloads"
DEFAULT_TEMP_DIR="/opt/easynas/temp"

# 端口配置
WEB_PORT=80
API_PORT=8080
SMB_PORT=445

# 实际使用的目录（可配置）
DATA_DIR=""
DOWNLOADS_DIR=""
TEMP_DIR=""

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }
log_success(){ echo -e "${GREEN}[✓]${NC} $1"; }

show_banner() {
    echo ""
    echo "=========================================="
    echo "        EasyNAS 一键部署脚本"
    echo "=========================================="
    echo ""
}

show_help() {
    echo "用法: sudo $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  install     安装并部署 EasyNAS"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  logs        查看日志"
    echo "  status      查看状态"
    echo "  uninstall   卸载 EasyNAS"
    echo ""
    echo "安装选项:"
    echo "  --data-dir        数据目录（任务记录、设置文件）"
    echo "  --downloads-dir   下载目录（保存下载的文件，提供 Samba 共享）"
    echo "  --temp-dir        临时目录（下载缓存）"
    echo ""
    echo "示例:"
    echo "  sudo $0 install                                    # 使用默认目录"
    echo "  sudo $0 install --downloads-dir /mnt/hdd/downloads # 自定义下载目录"
    echo ""
    echo "说明:"
    echo "  源码目录: 脚本所在目录"
    echo "  数据目录: /opt/easynas/data"
    echo "  下载目录: /opt/easynas/downloads (Samba 共享目录)"
    echo "  临时目录: /opt/easynas/temp"
    echo ""
}

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 用户运行此脚本"
        log_info "提示: 使用 'sudo $0' 执行"
        exit 1
    fi
}

# 检查端口
check_port() {
    local port=$1
    if ss -tuln 2>/dev/null | grep -q ":${port} "; then
        log_error "端口 ${port} 已被占用"
        return 1
    fi
    return 0
}

check_ports() {
    log_step "检查端口..."
    local failed=false

    for port in $WEB_PORT $API_PORT $SMB_PORT; do
        if ! check_port $port; then
            failed=true
        fi
    done

    if $failed; then
        log_error "端口冲突，请先停止占用端口的服务"
        exit 1
    fi
    log_success "端口检查通过"
}

# 检查目录
check_directory() {
    local dir=$1
    local name=$2

    if [ -z "$dir" ]; then
        log_error "${name} 未指定"
        return 1
    fi

    # 如果目录不存在，创建它
    if [ ! -d "$dir" ]; then
        log_info "创建目录: $dir"
        mkdir -p "$dir"
    fi

    # 检查是否可写
    if [ ! -w "$dir" ]; then
        log_error "目录不可写: $dir"
        return 1
    fi

    log_success "${name}: $dir"
    return 0
}

check_directories() {
    log_step "检查目录..."

    local failed=false

    if ! check_directory "$DATA_DIR" "数据目录"; then
        failed=true
    fi

    if ! check_directory "$DOWNLOADS_DIR" "下载目录"; then
        failed=true
    fi

    if ! check_directory "$TEMP_DIR" "临时目录"; then
        failed=true
    fi

    if $failed; then
        log_error "目录检查失败"
        exit 1
    fi
}

# 安装 Docker
install_docker() {
    if command -v docker &> /dev/null; then
        log_success "Docker 已安装: $(docker --version)"
        return
    fi

    log_step "安装 Docker..."

    apt-get update
    apt-get install -y ca-certificates curl gnupg lsb-release

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    systemctl enable docker
    systemctl start docker

    log_success "Docker 安装完成"
}

# 准备代码目录
prepare_code() {
    log_step "准备代码..."

    # 使用脚本所在目录
    cd "$SCRIPT_DIR"

    # 检查源码完整性
    if [ ! -f "$SCRIPT_DIR/Dockerfile" ] || [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
        log_error "源码目录不完整，缺少必要文件"
        exit 1
    fi

    log_success "使用源码目录: $SCRIPT_DIR"
}

# 生成 docker-compose.yml
generate_docker_compose() {
    log_step "生成配置..."

    cat > "${SCRIPT_DIR}/docker-compose.yml" << EOF
services:
  easynas:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: easynas
    restart: unless-stopped
    ports:
      - "${WEB_PORT}:80"
      - "${API_PORT}:8080"
      - "${SMB_PORT}:445"
      - "139:139"
    volumes:
      - ${DATA_DIR}:/app/data
      - ${DOWNLOADS_DIR}:/app/downloads
      - ${TEMP_DIR}:/app/temp
    environment:
      - PYTHONUNBUFFERED=1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

networks:
  default:
    name: easynas-network
EOF

    log_success "配置已生成"
}

# 构建镜像
build_image() {
    log_step "构建 Docker 镜像..."

    cd "$SCRIPT_DIR"
    docker compose build --no-cache

    log_success "镜像构建完成"
}

# 启动服务
start_services() {
    log_step "启动服务..."

    cd "$SCRIPT_DIR"
    docker compose up -d

    log_success "服务启动完成"
}

# 配置防火墙
setup_firewall() {
    if command -v ufw &> /dev/null; then
        if ufw status | grep -q "Status: active"; then
            ufw allow $WEB_PORT/tcp comment "EasyNAS Web" 2>/dev/null || true
            ufw allow $API_PORT/tcp comment "EasyNAS API" 2>/dev/null || true
            ufw allow $SMB_PORT/tcp comment "EasyNAS SMB" 2>/dev/null || true
        fi
    fi
}

show_result() {
    echo ""
    echo "=========================================="
    echo "        部署完成!"
    echo "=========================================="
    echo ""
    echo "访问地址:"
    echo "  Web 管理:  http://服务器IP"
    echo "  网络共享:  \\\\服务器IP\\downloads"
    echo ""
    echo "目录映射:"
    echo "  源码目录:   ${SCRIPT_DIR}"
    echo "  数据目录:   ${DATA_DIR}"
    echo "  下载目录:   ${DOWNLOADS_DIR}"
    echo "  临时目录:   ${TEMP_DIR}"
    echo ""
    echo "默认账号: admin / 111111"
    echo "首次登录后请修改密码！"
    echo ""
    echo "管理命令:"
    echo "  cd ${SCRIPT_DIR}"
    echo "  sudo ./deploy.sh status   # 查看状态"
    echo "  sudo ./deploy.sh logs     # 查看日志"
    echo "  sudo ./deploy.sh restart  # 重启"
    echo "  sudo ./deploy.sh stop     # 停止"
    echo ""
}

# 一键安装
do_install() {
    show_banner
    check_root
    check_ports
    check_directories
    install_docker
    prepare_code
    generate_docker_compose
    build_image
    start_services
    setup_firewall
    show_result
}

# 停止
do_stop() {
    cd "$SCRIPT_DIR" 2>/dev/null || exit 1
    docker compose down 2>/dev/null || true
    log_success "服务已停止"
}

# 启动
do_start() {
    cd "$SCRIPT_DIR" 2>/dev/null || exit 1
    docker compose up -d
    log_success "服务已启动"
}

# 重启
do_restart() {
    do_stop
    sleep 2
    do_start
}

# 日志
do_logs() {
    cd "$SCRIPT_DIR" 2>/dev/null || exit 1
    docker compose logs -f
}

# 状态
do_status() {
    echo ""
    echo "=========================================="
    echo "        EasyNAS 服务状态"
    echo "=========================================="
    echo ""

    cd "$SCRIPT_DIR" 2>/dev/null || exit 1

    if docker compose ps 2>/dev/null | grep -q easynas; then
        docker compose ps
        echo ""
        if curl -sf http://localhost:${API_PORT}/api/health &>/dev/null; then
            log_success "API 服务正常"
        else
            log_warn "API 服务可能未就绪"
        fi
    else
        log_warn "服务未运行"
    fi
    echo ""
}

# 卸载
do_uninstall() {
    echo ""
    log_warn "即将卸载 EasyNAS..."
    echo ""

    read -p "确认卸载? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        exit 0
    fi

    log_step "正在卸载..."

    cd "$SCRIPT_DIR" 2>/dev/null || true
    docker compose down --rmi local 2>/dev/null || true

    # 删除数据目录
    rm -rf "$DATA_DIR" 2>/dev/null || true
    rm -rf "$DOWNLOADS_DIR" 2>/dev/null || true
    rm -rf "$TEMP_DIR" 2>/dev/null || true

    log_success "卸载完成"
    log_info "数据目录已删除"
    echo ""
}

# 解析参数
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --data-dir)
                DATA_DIR="$2"
                shift 2
                ;;
            --downloads-dir)
                DOWNLOADS_DIR="$2"
                shift 2
                ;;
            --temp-dir)
                TEMP_DIR="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    # 设置默认值
    DATA_DIR="${DATA_DIR:-${DEFAULT_DATA_DIR}}"
    DOWNLOADS_DIR="${DOWNLOADS_DIR:-${DEFAULT_DOWNLOADS_DIR}}"
    TEMP_DIR="${TEMP_DIR:-${DEFAULT_TEMP_DIR}}"
}

# 主入口
parse_args "$@"

case "${1:-}" in
    install)   do_install ;;
    start)     do_start ;;
    stop)      do_stop ;;
    restart)   do_restart ;;
    logs)      do_logs ;;
    status)    do_status ;;
    uninstall) do_uninstall ;;
    help|--help|-h) show_help ;;
    *)         show_help ;;
esac
