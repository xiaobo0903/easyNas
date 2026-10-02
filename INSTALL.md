# EasyNAS 安装指南

## 环境要求

- Ubuntu 20.04+ / Debian 10+
- Docker 20.10+
- 80、8080、445、139 端口未被占用

## 一键安装

```bash
# 先克隆代码
git clone https://gitee.com/xiaobo0903/easy-nas.git
cd easy-nas

# 开始安装
sudo ./deploy.sh install --downloads-dir /你的大容量硬盘路径
```

## 目录说明

EasyNAS 使用三个目录：

| 目录 | 说明 | 建议 |
|------|------|------|
| `--data-dir` | 任务记录、应用设置 | 小容量即可 |
| `--downloads-dir` | 下载的文件，提供 Samba 共享 | **大容量存储** |
| `--temp-dir` | 下载缓存 | 小容量即可 |

> **重要**：`--downloads-dir` 是 Samba 网络共享的目录，建议挂载大容量硬盘或 RAID

## 自定义目录

```bash
# 示例：下载目录使用 /mnt/hdd/downloads
sudo ./deploy.sh install --downloads-dir /mnt/hdd/downloads

# 或挂载一块专门的硬盘
sudo ./deploy.sh install \
  --data-dir /opt/easynas/data \
  --downloads-dir /mnt/disk2/downloads \
  --temp-dir /opt/easynas/temp
```

## 服务访问

| 服务 | 地址 |
|------|------|
| Web 管理界面 | http://服务器IP |
| 网络共享（Samba） | 在 Web 界面「共享设置」中开启后可用 |

> 开启网络共享后，Windows/macOS/手机可通过 SMB 协议访问下载目录中的文件

## 默认账号

- 用户名：`admin`
- 密码：`111111`

> 首次登录后请修改密码！

## 网络共享连接

| 系统 | 操作步骤 |
|------|----------|
| macOS | Finder → 前往 → 连接服务器 → 输入 `smb://服务器IP` |
| Windows | 文件资源管理器地址栏输入 `\\服务器IP` |
| 手机 | 文件管理器添加 SMB 服务器 |

> **首次使用**：在 Web 界面「共享设置」中开启网络共享开关，才能通过 Samba 访问文件

## 管理命令

```bash
cd /opt/easy-nas

sudo ./deploy.sh start     # 启动
sudo ./deploy.sh stop      # 停止
sudo ./deploy.sh restart   # 重启
sudo ./deploy.sh logs      # 查看日志
sudo ./deploy.sh status    # 查看状态
sudo ./deploy.sh uninstall # 卸载
```

## 常见问题

**端口被占用？**

```bash
# 查看端口占用
ss -tuln | grep -E '80|8080|445|139'

# 停止占用端口的服务
sudo systemctl stop apache2 nginx smbd
```

**如何备份？**

```bash
tar -czvf easy-nas-backup.tar.gz /opt/easynas/
```

**如何更新？**

```bash
cd /opt/easy-nas
git pull
sudo ./deploy.sh restart
```
