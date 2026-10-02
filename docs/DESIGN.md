# EasyDown 下载管理器设计文档

## 1. 项目概述

EasyDown 是一个容器化的通用下载服务，支持 HTTP/HTTPS、FTP、BT (.torrent)、Magnet 磁力链接、Thunder 迅雷链接等常见下载协议。前端采用 Vue3，后端采用 Python Flask + aria2。

### 1.1 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Vue3 Frontend                         │
│              (管理界面 + 任务列表 + 状态管理)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP REST API / WebSocket
┌─────────────────────▼───────────────────────────────────────┐
│                   Python Flask API Server                    │
│    - 任务管理 (CRUD)                                         │
│    - 实时进度推送                                            │
│    - 存储下载历史/配置                                        │
└─────────────────────┬───────────────────────────────────────┘
                      │ subprocess / RPC
┌─────────────────────▼───────────────────────────────────────┐
│                  aria2c Daemon (子进程)                      │
│    - BT/磁力下载 (libtorrent 引擎)                           │
│    - DHT 网络支持                                            │
│    - HTTP/FTP 分片下载                                       │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
/Volumes/odisk/easydown/
├── frontend/                 # Vue3 前端项目
│   ├── src/
│   │   ├── App.vue           # 主界面组件
│   │   ├── api/index.js      # API 调用封装
│   │   ├── stores/tasks.js   # Pinia 状态管理
│   │   └── components/
│   │       ├── TaskTable.vue      # 任务列表组件
│   │       └── AddTaskModal.vue   # 新增任务弹窗
│   └── dist/                 # 构建产物
├── backend-py/               # Python 后端
│   ├── app.py                # Flask 主程序
│   └── requirements.txt      # Python 依赖
├── data/                     # 数据目录
│   ├── dht.dat              # DHT 网络状态
│   └── downloads/           # 下载文件目录
├── docs/
│   └── DESIGN.md            # 本文档
└── .vscode/
    └── launch.json          # VSCode 调试配置
```

---

## 2. 功能列表

### 2.1 下载协议支持

| 协议 | 处理方式 | 说明 |
|------|----------|------|
| HTTP/HTTPS | Python requests | 多线程分片下载，支持断点续传 |
| FTP | Python requests | 被动模式 |
| BT (.torrent) | aria2c (libtorrent) | DHT、PeX、端口转发 |
| Magnet | aria2c (DHT) | 自动从 DHT 网络获取种子信息 |
| Thunder (迅雷) | Python 解码 | `thunder://` → 原始 URL |

### 2.2 任务管理

- [x] 新增下载任务 (支持 URL 自动识别类型)
- [x] 任务列表展示 (名称、进度、状态、大小、速度)
- [x] 暂停/继续任务
- [x] 删除任务 (同时删除文件)
- [x] 批量操作 (全选、批量暂停、批量删除)
- [x] 实时进度更新 (每秒轮询)
- [x] 下载速度显示

### 2.3 BT/磁力下载配置 (aria2)

```yaml
# 连接配置
max-connection-per-server: 16  # 单服务器最大连接数
split: 16                      # 分片数
max-concurrent-downloads: 5    # 最大并发下载数

# BT 特殊配置
bt-max-peers: 100              # 最大 peer 数
bt-seed-unverified: true       # 边下载边做种
dht: true                      # 启用 DHT
dht-file-path: /data/dht.dat   # DHT 状态文件
dht-listen-port: 6881          # DHT 监听端口

# 速度配置
max-overall-download-limit: 0  # 0 = 无限制
lowest-speed-limit: 0          # 最低速度限制

# 其他
continue: true                 # 断点续传
check-integrity: false         # 下载完成后不验证完整性
```

---

## 3. API 设计

### 3.1 基础信息

- 基础路径: `http://localhost:8080/api`
- 数据格式: JSON
- 认证: 暂不需要

### 3.2 任务接口

#### 3.2.1 获取任务列表

```
GET /api/tasks

Response:
{
  "tasks": [
    {
      "id": "task_1",
      "name": "Ubuntu 22.04 LTS",
      "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04-desktop-amd64.iso",
      "type": "http",
      "status": "downloading",
      "progress": 67.5,
      "downloaded": 2147483648,
      "totalSize": 3188234240,
      "speed": 5242880,
      "connections": 16,
      "errorMsg": "",
      "savePath": "/Volumes/odisk/easydown/downloads",
      "createdAt": 1712345678.123,
      "updatedAt": 1712345679.456
    }
  ],
  "total": 1
}
```

#### 3.2.2 新增任务

```
POST /api/tasks

Body:
{
  "url": "https://example.com/file.zip",
  "name": "自定义文件名",      // 可选
  "savePath": "/path/to/save"  // 可选
}

Response:
{
  "id": "task_2",
  "name": "file.zip",
  "url": "https://example.com/file.zip",
  "type": "http",
  "status": "downloading",
  ...
}
```

#### 3.2.3 获取单个任务

```
GET /api/tasks/:id

Response: 单个任务对象
```

#### 3.2.4 暂停任务

```
POST /api/tasks/:id/pause

Response:
{
  "message": "paused"
}
```

#### 3.2.5 继续任务

```
POST /api/tasks/:id/resume

Response:
{
  "message": "resumed"
}
```

#### 3.2.6 删除任务

```
DELETE /api/tasks/:id

Response:
{
  "message": "removed"
}
```

#### 3.2.7 暂停全部

```
POST /api/tasks/pause-all

Response:
{
  "message": "all paused"
}
```

#### 3.2.8 继续全部

```
POST /api/tasks/resume-all

Response:
{
  "message": "all resumed"
}
```

### 3.3 其他接口

#### 3.3.1 下载统计

```
GET /api/stats

Response:
{
  "downloadSpeed": 5242880,
  "uploadSpeed": 102400,
  "numDownloads": 3,
  "numSeeds": 1
}
```

#### 3.3.2 获取设置

```
GET /api/settings

Response:
{
  "maxConcurrent": 5,
  "maxSpeed": 0,
  "maxConnections": 16,
  "savePath": "/Volumes/odisk/easydown/downloads",
  "btPort": 6881,
  "dhtEnabled": true,
  "seedRatio": 0,
  "seedTime": 0
}
```

#### 3.3.3 更新设置

```
PUT /api/settings

Body:
{
  "maxSpeed": 10485760,  // 10MB/s
  "maxConcurrent": 3
}
```

#### 3.3.4 健康检查

```
GET /api/health

Response:
{
  "status": "ok"
}
```

---

## 4. 数据模型

### 4.1 DownloadTask

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 任务唯一标识，格式 `task_N` |
| name | string | 文件名 |
| url | string | 原始下载链接 |
| type | string | 下载类型: `http`, `ftp`, `bt`, `magnet` |
| status | enum | `idle`, `downloading`, `paused`, `completed`, `failed`, `seeding` |
| progress | float | 下载进度 0-100 |
| downloaded | int | 已下载字节数 |
| totalSize | int | 文件总字节数 |
| speed | int | 当前速度 (bytes/s) |
| connections | int | 当前连接数 |
| errorMsg | string | 错误信息 |
| savePath | string | 保存路径 |
| createdAt | float | 创建时间戳 |
| updatedAt | float | 更新时间戳 |
| aria2_gid | string | aria2 内部 GID |

### 4.2 DownloadStatus 枚举

```python
class DownloadStatus(Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SEEDING = "seeding"
```

---

## 5. 界面设计

### 5.1 布局

```
┌──────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────────────────────────────┐  │
│ │          │ │  下载管理器              [+ 新增任务]   │  │
│ │ 下载任务 │ ├────────────────────────────────────────┤  │
│ │ 已下载   │ │ [全选] [暂停] [开始] [停止] [删除]     │  │
│ │ 任务设置 │ ├────────────────────────────────────────┤  │
│ │          │ │ ☑ │ 文件名    │ 进度  │ 状态  │ 大小 │  │  │
│ │          │ │ ☐ │ Ubuntu   │ 67%   │ 下载中│ 2.1GB│  │  │
│ │          │ │ ☐ │ VSCode   │ 100%  │ 已完成│ 86MB │  │  │
│ │          │ │ ☐ │ Figma    │ 0%    │ 已暂停│ —/124MB│ │  │
│ │          │ └────────────────────────────────────────┘  │
│ └──────────┘                                              │
└──────────────────────────────────────────────────────────┘
```

### 5.2 颜色规范

支持浅色/深色两种主题，默认浅色，可通过侧边栏底部切换。

```css
/* 浅色主题 (默认) */
:root {
  --bg: #f5f5f7;
  --surface: #ffffff;
  --surface-hover: #e8e8ec;
  --fg: #1d1d1f;
  --muted: #6e6e73;
  --border: #d2d2d7;
  --accent: #0071e3;
  --accent-hover: #0077ed;
  --success: #34c759;
  --warning: #ff9f0a;
  --danger: #ff3b30;
}

/* 深色主题 */
[data-theme="dark"] {
  --bg: #0f0f12;
  --surface: #18181c;
  --surface-hover: #222228;
  --fg: #e8e8ed;
  --muted: #6b6b78;
  --border: #2a2a32;
  --accent: #4f8fff;
  --accent-hover: #6ba3ff;
  --success: #34d399;
  --warning: #fbbf24;
  --danger: #f87171;
}
```

### 5.3 新增任务弹窗

```
┌─────────────────────────────────────┐
│  新增下载任务                   [×]  │
├─────────────────────────────────────┤
│  下载链接                          │
│  ┌─────────────────────────────┐   │
│  │ https://example.com/file.zip│   │
│  └─────────────────────────────┘   │
│                                     │
│  文件名（可选）                      │
│  ┌─────────────────────────────┐   │
│  │ 留空则自动从链接提取         │   │
│  └─────────────────────────────┘   │
│                                     │
│  保存路径（可选）                    │
│  ┌─────────────────────────────┐   │
│  │ 默认保存到下载目录           │   │
│  └─────────────────────────────┘   │
│                                     │
│  支持 HTTP/HTTPS/FTP/Magnet/Torrent │
│                              [取消] [确定] │
└─────────────────────────────────────┘
```

---

## 6. 容器化部署

### 6.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 aria2
RUN apt-get update && apt-get install -y aria2 && rm -rf /var/lib/apt/lists/*

# 复制应用
COPY backend-py/ /app/
COPY frontend/dist/ /app/static/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建数据目录
RUN mkdir -p /data/downloads /data

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["python", "app.py"]
```

### 6.2 docker-compose.yml

```yaml
version: '3.8'
services:
  easydown:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./downloads:/data/downloads
    restart: unless-stopped
```

---

## 7. 协议详解

### 7.1 Magnet 链接解析

Magnet 链接格式:
```
magnet:?xt=urn:btih:HASH&dn=NAME&tr=TRACKER_URL
```

解析步骤:
1. 提取 `xt` (exact topic) 中的 info hash
2. 提取 `dn` (display name) 作为文件名
3. 提取 `tr` (tracker) 作为 tracker 服务器
4. 通过 DHT 网络获取 peers

### 7.2 Thunder 链接解码

Thunder 链接格式: `thunder://BASE64(EX + URL)`

解码步骤:
1. 去掉 `thunder://` 前缀
2. Base64 解码
3. 去掉头尾的 `EX`

### 7.3 BT 下载优化

- **DHT (Distributed Hash Table)**: 无 tracker 情况下通过 DHT 网络发现 peers
- **PeX (Peer Exchange)**: 从已有 peers 交换其他 peers 信息
- **LSD (Local Service Discovery)**: 发现本地网络中的 peers
- **端口映射**: UPnP/NAT-PMP 自动端口转发 (需要路由器支持)

---

## 8. 待完成功能

- [ ] WebSocket 实时推送替代轮询
- [ ] 设置面板 (速度限制、并发数等)
- [ ] 下载历史记录
- [ ] 文件管理 (打开所在文件夹、删除文件)
- [ ] 任务重试
- [ ] 用户认证
- [ ] 国际化 (i18n)

---

## 9. 常见问题

### 9.1 BT 下载速度慢
- 检查 `bt-max-peers` 设置 (建议 50-100)
- 确认防火墙开放了 6881-6891 端口
- 尝试添加更多 tracker
- 等待 DHT 网络发现有更多 peers

### 9.2 Magnet 链接无法获取 metadata
- Magnet 需要先从 DHT 网络获取种子信息，可能需要几分钟
- 检查 `dht-file-path` 是否正确配置
- 确保 DHT 端口 (6881) 已开放

### 9.3 HTTP 下载失败
- 检查 URL 是否可访问
- 确认服务器是否支持断点续传 (Accept-Ranges header)
- 尝试设置 User-Agent 和 Referer
