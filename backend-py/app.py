"""
EasyNAS - Simple Home NAS Solution
Uses: requests (HTTP/FTP), aria2c CLI (BT/Magnet)
"""

import os
import sys
import time
import json
import logging
import subprocess
import threading
import base64
import urllib.parse
import re
import hashlib
import secrets
import shutil
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum

import jwt
from flask import Flask, jsonify, request, send_file, g
from flask_cors import CORS

# JWT configuration
JWT_SECRET = secrets.token_hex(32)
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 3

# Fixed downloads directory (relative to project root)
DOWNLOADS_DIR = "downloads"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Routes that don't require JWT validation
_JWT_EXEMPT_ROUTES = {'/api/auth/login', '/api/auth/status', '/api/health'}

def create_token():
    """Create a JWT token with 3 hour expiration"""
    payload = {
        'exp': time.time() + (JWT_EXPIRATION_HOURS * 60 * 60),
        'iat': time.time()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token):
    """Verify JWT token and return payload if valid"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@app.before_request
def check_jwt():
    """Check if JWT token is valid"""
    # Skip exempt routes
    if request.path in _JWT_EXEMPT_ROUTES:
        return None

    # Skip OPTIONS requests (CORS preflight)
    if request.method == 'OPTIONS':
        return None

    # Get token from header
    token = request.headers.get('X-Session-Token', '')
    if not token:
        return jsonify({'error': '未登录或会话已过期', 'code': 'SESSION_EXPIRED'}), 401

    # Verify token
    payload = verify_token(token)
    if not payload:
        return jsonify({'error': '会话已过期，请重新登录', 'code': 'SESSION_EXPIRED'}), 401

    return None

# =============================================================================
# Download Types
# =============================================================================

class DownloadStatus(Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SEEDING = "seeding"

# =============================================================================
# Task Model
# =============================================================================

@dataclass
class DownloadTask:
    id: str
    name: str
    url: str
    download_type: str  # http, ftp, bt, magnet
    status: DownloadStatus = DownloadStatus.IDLE
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: int = 0  # bytes per second
    upload_speed: int = 0  # bytes per second (for BT/seeding)
    connections: int = 0
    error_msg: str = ""
    save_path: str = "downloads"
    created_at: float = field(default_factory=time.time)
    aria2_gid: str = ""  # Aria2 GID for BT/Magnet
    process: any = None  # For HTTP download thread
    metadata_received_at: float = 0  # Track when metadata was received (for magnet)
    user_paused: bool = False  # Track if user manually paused this task
    completed_at: float = 0  # Track when download was completed
    target_dir: str = ""  # 最终保存目录：下载完成后文件会被移动到这里（不存在则新建）
    final_paths: list = field(default_factory=list)  # 完成后文件/文件夹在目标目录中的实际路径（删除任务时使用）
    _stop_event: any = field(default_factory=threading.Event)  # For HTTP download pause

# =============================================================================
# Download Manager
# =============================================================================

class DownloadManager:
    def __init__(self):
        # Fixed downloads directory (always use DOWNLOADS_DIR)
        self._downloads_dir = self._get_abs_path(DOWNLOADS_DIR)
        # _temp_path is the temporary download directory for aria2
        self._temp_path = self._get_abs_path("temp")
        # aria2 and new tasks use temp path initially
        self.save_path = self._temp_path
        self.tasks: Dict[str, DownloadTask] = {}
        self.next_id = 1
        self._aria2_session: Optional[subprocess.Popen] = None
        self._aria2_port = 6800
        self._lock = threading.Lock()
        self._data_dir = self._get_abs_path("data")
        self._state_file = os.path.join(self._data_dir, "tasks.json")
        self._settings_file = os.path.join(self._data_dir, "settings.json")

        # Create directories
        os.makedirs(self._temp_path, exist_ok=True)
        os.makedirs(self._data_dir, exist_ok=True)
        os.makedirs(self._downloads_dir, exist_ok=True)

        # Load settings
        self._settings = self._load_settings()

        # Initialize auth
        self._init_auth()

        # Start aria2 RPC daemon
        self._start_aria2()

        # Restore tasks from saved state
        self._restore_tasks()

    def _load_settings(self) -> dict:
        """Load settings from file"""
        default_settings = {
            'maxConcurrent': 5,
            'deleteConfirm': True,
            'deleteWithFiles': True,
            'savePath': 'downloads',
            'shareEnabled': False,
            'shareName': 'easynas',
            'shareDescription': 'EasyNAS Download Share',
            'guestAccess': True,
            'shareUsername': '',
            'sharePassword': '',
            'shareReadOnly': False,
        }
        if not os.path.exists(self._settings_file):
            return default_settings
        try:
            with open(self._settings_file, 'r') as f:
                settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                return {**default_settings, **settings}
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return default_settings

    def _save_settings(self):
        """Save settings to file"""
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(self._settings, f)
            logger.info("Settings saved")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def _get_abs_path(self, path: str) -> str:
        """Convert path to absolute path based on project directory.

        If path is already absolute (starts with /), return as-is.
        Otherwise, treat as relative to the project directory (backend-py/ subdirectory).
        """
        if os.path.isabs(path):
            return path
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(backend_dir)
        result = os.path.join(project_root, path)
        result = os.path.normpath(result)
        logger.info(f"_get_abs_path('{path}'): backend_dir={backend_dir}, project_root={project_root}, result={result}")
        return result

    def _validate_path(self, path: str) -> bool:
        """Validate path exists and is writable, create if needed"""
        if not path:
            return False
        try:
            abs_path = self._get_abs_path(path)
            os.makedirs(abs_path, exist_ok=True)
            test_file = os.path.join(abs_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"Path validation failed for {path}: {e}")
            return False

    def _hash_password(self, password: str) -> str:
        """Hash a password with a random salt"""
        salt = secrets.token_hex(16)
        hash_val = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${hash_val.hex()}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against a stored hash"""
        try:
            salt, hash_val = stored_hash.split('$')
            expected = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return secrets.compare_digest(expected.hex(), hash_val)
        except:
            return False

    def _init_auth(self):
        """Initialize auth - create admin user if not exists"""
        if 'passwordHash' not in self._settings:
            self._settings['passwordHash'] = self._hash_password('111111')
            self._settings['mustChangePassword'] = True
            self._save_settings()

    def verify_login(self, password: str) -> dict:
        """Verify login credentials, returns user info or None"""
        password_hash = self._settings.get('passwordHash', '')
        if self._verify_password(password, password_hash):
            # If password is 111111, always require change
            must_change = (password == '111111')
            return {
                'username': 'admin',
                'mustChangePassword': must_change
            }
        return None

    def change_password(self, old_password: str, new_password: str) -> dict:
        """Change password - requires old password"""
        password_hash = self._settings.get('passwordHash', '')
        if not self._verify_password(old_password, password_hash):
            return {'success': False, 'error': '旧密码错误'}

        self._settings['passwordHash'] = self._hash_password(new_password)
        self._settings['mustChangePassword'] = False
        self._save_settings()
        return {'success': True}

    def _check_samba_installed(self) -> bool:
        """Check if Samba is properly installed (not just macOS built-in)"""
        # Check for smbpasswd which only exists in full Samba installations
        result = subprocess.run(['which', 'smbpasswd'], capture_output=True)
        if result.returncode == 0:
            return True
        # Check if it's macOS built-in smbd (limited)
        result = subprocess.run(['smbd', '--help'], capture_output=True, text=True)
        if 'no-symlinks' in result.stdout.lower():
            # This is macOS built-in version, not full Samba
            return False
        return False

    def _is_linux_smbd(self) -> bool:
        """Check if using Linux smbd with full config support"""
        result = subprocess.run(['smbd', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version_output = result.stdout.lower()
            # Linux Samba shows version like "smbd version X.XX.X"
            return 'version' in version_output and 'samba' in version_output
        return False

    def _get_smb_conf_path(self) -> str:
        """Get path to smb.conf"""
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'smb.conf')

    def _generate_smb_conf(self) -> str:
        """Generate smb.conf based on current settings"""
        share_path = self._downloads_dir
        share_name = self._settings.get('shareName', 'easynas')
        share_desc = self._settings.get('shareDescription', 'EasyNAS Download Share')
        guest_access = self._settings.get('guestAccess', True)
        read_only = self._settings.get('shareReadOnly', False)
        username = self._settings.get('shareUsername', '')

        conf = f"""[global]
   netbios name = {share_name}
   server string = {share_name} Samba Server
   server role = standalone server
   map to guest = Bad Password
   dns proxy = No
   log file = /tmp/sambad.log
   max log size = 1000
   socket options = TCP_NODELAY IPTOS_LOWDELAY

[{share_name}]
   path = {share_path}
   comment = {share_desc}
   browseable = Yes
   read only = {'Yes' if read_only else 'No'}
   create mask = 0664
   directory mask = 0775
"""

        if guest_access:
            conf += "   guest only = Yes\n   guest ok = Yes\n"
        else:
            if username:
                conf += f"   valid users = {username}\n"

        return conf

    def _reload_smb_conf(self):
        """Regenerate and reload Samba configuration"""
        try:
            # Write new smb.conf
            smb_conf = self._get_smb_conf_path()
            with open(smb_conf, 'w') as f:
                f.write(self._generate_smb_conf())
            # Reload Samba config
            subprocess.run(['smbcontrol', 'smbd', 'reload-config'], capture_output=True)
            logger.info("Samba config reloaded")
        except Exception as e:
            logger.error(f"Failed to reload samba config: {e}")

    def enable_share(self) -> dict:
        """Enable file sharing"""
        if not self._check_samba_installed():
            return {'success': False, 'error': 'Samba is not installed. Please install with: brew install samba'}

        try:
            # Generate smb.conf
            smb_conf = self._get_smb_conf_path()
            os.makedirs(os.path.dirname(smb_conf), exist_ok=True)
            with open(smb_conf, 'w') as f:
                f.write(self._generate_smb_conf())

            # Create share directory
            share_path = self._downloads_dir
            os.makedirs(share_path, exist_ok=True)

            # Set up user if needed
            guest_access = self._settings.get('guestAccess', True)
            if not guest_access:
                username = self._settings.get('shareUsername', '')
                password = self._settings.get('sharePassword', '')
                if username and password:
                    # Create or update user
                    try:
                        subprocess.run(['useradd', '-M', '-s', '/usr/sbin/nologin', username], capture_output=True)
                    except:
                        pass
                    # Set password
                    proc = subprocess.Popen(['smbpasswd', '-a', '-s', username],
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    proc.communicate(input=f"{password}\n{password}\n".encode())

            # Stop smbd if running
            subprocess.run(['pkill', 'smbd'], capture_output=True)
            subprocess.run(['pkill', 'nmbd'], capture_output=True)
            time.sleep(1)

            # Start smbd and nmbd with custom config
            subprocess.Popen(['smbd', '-s', smb_conf, '-F'],
                           stdout=open('/tmp/samba.log', 'w'),
                           stderr=subprocess.STDOUT)
            subprocess.Popen(['nmbd', '-s', smb_conf, '-F'],
                           stdout=open('/tmp/samba.log', 'w'),
                           stderr=subprocess.STDOUT)

            self._settings['shareEnabled'] = True
            self._save_settings()

            return {'success': True}
        except Exception as e:
            logger.error(f"Failed to enable share: {e}")
            return {'success': False, 'error': str(e)}

    def disable_share(self) -> dict:
        """Disable file sharing"""
        try:
            subprocess.run(['pkill', 'smbd'], capture_output=True)
            subprocess.run(['pkill', 'nmbd'], capture_output=True)
            self._settings['shareEnabled'] = False
            self._save_settings()
            return {'success': True}
        except Exception as e:
            logger.error(f"Failed to disable share: {e}")
            return {'success': False, 'error': str(e)}

    def get_share_status(self) -> dict:
        """Get current share status"""
        # Check if smbd is running (for Linux with full Samba)
        result = subprocess.run(['pgrep', '-f', 'smbd.*easynas'], capture_output=True)
        is_running = result.returncode == 0
        # Also check for any smbd process if full Samba is installed
        if not is_running and self._check_samba_installed():
            result = subprocess.run(['pgrep', '-f', 'smbd'], capture_output=True)
            is_running = result.returncode == 0

        return {
            'installed': self._check_samba_installed(),
            'running': is_running,
            'enabled': self._settings.get('shareEnabled', False),
        }

    @property
    def _max_concurrent(self) -> int:
        return self._settings.get('maxConcurrent', 5)

    def get_settings(self) -> dict:
        """Get current settings"""
        return {
            'maxConcurrent': self._settings.get('maxConcurrent', 5),
            'deleteConfirm': self._settings.get('deleteConfirm', True),
            'deleteWithFiles': self._settings.get('deleteWithFiles', False),
            'savePath': DOWNLOADS_DIR,  # Always return fixed value
            'shareEnabled': self._settings.get('shareEnabled', False),
            'shareName': self._settings.get('shareName', 'easynas'),
            'shareDescription': self._settings.get('shareDescription', 'EasyNAS Download Share'),
            'guestAccess': self._settings.get('guestAccess', True),
            'shareUsername': self._settings.get('shareUsername', ''),
            'shareReadOnly': self._settings.get('shareReadOnly', False),
        }

    def update_settings(self, settings: dict):
        """Update settings"""
        if 'maxConcurrent' in settings:
            new_val = max(5, min(15, int(settings['maxConcurrent'])))
            if new_val != self._settings.get('maxConcurrent', 5):
                self._settings['maxConcurrent'] = new_val
                self._aria2_change_max_concurrent(new_val)
        if 'deleteConfirm' in settings:
            self._settings['deleteConfirm'] = bool(settings['deleteConfirm'])
        if 'deleteWithFiles' in settings:
            self._settings['deleteWithFiles'] = bool(settings['deleteWithFiles'])
        # savePath is now fixed, ignore any attempts to change it
        # Share settings
        if 'shareEnabled' in settings:
            self._settings['shareEnabled'] = bool(settings['shareEnabled'])
        share_name_changed = False
        if 'shareName' in settings:
            new_name = settings['shareName'].strip() or 'easynas'
            if new_name != self._settings.get('shareName', 'easynas'):
                self._settings['shareName'] = new_name
                share_name_changed = True
        if 'shareDescription' in settings:
            self._settings['shareDescription'] = settings['shareDescription'].strip()
        if 'guestAccess' in settings:
            self._settings['guestAccess'] = bool(settings['guestAccess'])
        if 'shareUsername' in settings:
            self._settings['shareUsername'] = settings['shareUsername'].strip()
        if 'sharePassword' in settings:
            self._settings['sharePassword'] = settings['sharePassword']
        if 'shareReadOnly' in settings:
            self._settings['shareReadOnly'] = bool(settings['shareReadOnly'])
        self._save_settings()

        # Regenerate smb.conf if share name or description changed
        if share_name_changed or 'shareDescription' in settings:
            self._reload_smb_conf()

    def _start_aria2(self):
        """Start aria2 RPC daemon"""
        try:
            # Kill any existing aria2 on this port
            subprocess.run(
                ["pkill", "-f", f"aria2c.*--rpc-listen-port={self._aria2_port}"],
                capture_output=True
            )
            time.sleep(0.5)

            # Start aria2
            max_concurrent = self._settings.get('maxConcurrent', 5)
            cmd = [
                "aria2c",
                "--enable-rpc",
                "--rpc-listen-port", str(self._aria2_port),
                "--rpc-allow-origin-all",
                "--dir", self.save_path,
                "--dht-file-path", os.path.join(self._data_dir, "dht.dat"),
                "--dht-listen-port", "6881",
                "--max-concurrent-downloads", str(max_concurrent),
                "--max-connection-per-server", "16",
                "--split", "16",
                "--bt-max-peers", "100",
                "--bt-seed-unverified=true",
                "--seed-time=0",  # 下载完成后不做种（0 = 完成即停止）
                "--continue=true",
                "--quiet"
            ]

            self._aria2_session = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1)  # Wait for aria2 to start

            logger.info(f"Aria2 started on port {self._aria2_port} with maxConcurrent={max_concurrent}")

        except FileNotFoundError:
            logger.error("aria2c not found! Please install aria2: brew install aria2")
        except Exception as e:
            logger.error(f"Failed to start aria2: {e}")

    def _collect_files_to_delete(self, task: DownloadTask) -> list:
        """Collect list of files to delete for a task"""
        files = []

        # 已完成并移动过的任务：直接使用移动后的实际路径
        if task.final_paths:
            return [p for p in task.final_paths if os.path.exists(p)]

        # For HTTP downloads, find the file by task name
        if task.download_type == 'http' and task.name:
            file_path = os.path.join(task.save_path, task.name)
            if os.path.exists(file_path):
                files.append(file_path)
            return files

        # For BT/Magnet downloads, get files from aria2 before removing
        if task.download_type in ('bt', 'magnet') and task.aria2_gid:
            status = self._aria2_get_status(task.aria2_gid)
            if status and 'files' in status:
                for file_info in status['files']:
                    file_path = file_info.get('path', '')
                    if file_path and os.path.exists(file_path) and '[METADATA]' not in file_path:
                        files.append(file_path)
                return files

        # Fallback: try to find files by task name pattern
        if task.name:
            for root, dirs, files_or_dirs in os.walk(task.save_path):
                for f in files_or_dirs:
                    if task.name in f and not f.endswith('.torrent'):
                        file_path = os.path.join(root, f)
                        if os.path.exists(file_path):
                            files.append(file_path)

        return files

    def _delete_files_list(self, file_paths: list):
        """Delete a list of files"""
        downloads_root = os.path.normpath(self._downloads_dir)
        temp_root = os.path.normpath(self._temp_path)
        for file_path in file_paths:
            try:
                if os.path.isdir(file_path) and not os.path.islink(file_path):
                    # 文件夹（多文件种子）：只允许删除下载目录/临时目录内部的内容
                    norm = os.path.normpath(file_path)
                    inside = any(norm.startswith(root + os.sep) for root in (downloads_root, temp_root))
                    if not inside:
                        logger.warning(f"Refuse to delete directory outside download dirs: {file_path}")
                        continue
                    shutil.rmtree(file_path)
                    logger.info(f"Deleted directory: {file_path}")
                elif os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")

        # Also clean up empty directories that might have been created for this task
        try:
            for root, dirs, files in os.walk(self.save_path, topdown=False):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    if os.path.isdir(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"Removed empty directory: {dir_path}")
        except Exception as e:
            logger.debug(f"Failed to clean up empty directories: {e}")

    # ------------------------------------------------------------------
    # 任务完成处理：停止做种 + 移动到指定目录
    # ------------------------------------------------------------------
    def _resolve_target_dir(self, save_path: str) -> str:
        """解析任务的最终保存目录。

        留空 -> 下载目录；填写 -> 下载目录下的子目录（也接受位于下载目录内的绝对路径）。
        不允许跳出下载目录（如 ../）。
        """
        base = os.path.normpath(self._downloads_dir)
        raw = (save_path or "").strip()
        if not raw:
            return base
        if os.path.isabs(raw) and (os.path.normpath(raw) == base or os.path.normpath(raw).startswith(base + os.sep)):
            return os.path.normpath(raw)
        rel = raw.strip('/').strip('\\')
        if not rel:
            return base
        target = os.path.normpath(os.path.join(base, rel))
        if target != base and not target.startswith(base + os.sep):
            raise ValueError("保存路径不合法：不能超出下载目录")
        return target

    def _is_task_work_dir(self, task: DownloadTask) -> bool:
        """task.save_path 是否是该任务独立的临时工作目录 temp/<task_id>"""
        work = os.path.normpath(task.save_path)
        return work == os.path.join(os.path.normpath(self._temp_path), task.id)

    def _unique_dest(self, target_dir: str, name: str) -> str:
        """目标已存在同名文件/文件夹时，自动改名为 'name (1)'，避免覆盖"""
        dst = os.path.join(target_dir, name)
        if not os.path.exists(dst):
            return dst
        stem, ext = os.path.splitext(name) if not os.path.isdir(os.path.join(target_dir, name)) else (name, "")
        i = 1
        while True:
            candidate = os.path.join(target_dir, f"{stem} ({i}){ext}")
            if not os.path.exists(candidate):
                return candidate
            i += 1

    def _stop_aria2_task(self, gid: str):
        """彻底停止并移除 aria2 里的任务 —— 即“停止做种”，同时释放文件句柄以便移动"""
        if not gid:
            return
        for method in ("aria2.forceRemove", "aria2.removeDownloadResult"):
            try:
                self._aria2_call(method, [gid])
            except Exception as e:
                logger.debug(f"{method} {gid} failed: {e}")
        logger.info(f"Stopped aria2 task (no more seeding): {gid}")

    def _move_downloaded_files(self, task: DownloadTask, paths: list = None) -> bool:
        """把下载完成的内容从工作目录移动到任务指定的目录（不存在则新建）。成功返回 True"""
        target = os.path.normpath(task.target_dir or self._downloads_dir)
        src_dir = os.path.normpath(task.save_path)
        if src_dir == target:
            return True  # 已经在目标目录，无需移动
        is_work_dir = self._is_task_work_dir(task)  # 必须在改 save_path 之前判断

        try:
            os.makedirs(target, exist_ok=True)

            # 1) 找出需要移动的“顶层条目”（单个文件，或种子的根文件夹）
            entries = []
            if task.download_type == 'http':
                if task.name:
                    entries.append(os.path.join(src_dir, task.name))
            else:
                for p in (paths or []):
                    if not p:
                        continue
                    try:
                        rel = os.path.relpath(os.path.normpath(p), src_dir)
                    except ValueError:
                        continue
                    if rel.startswith('..'):
                        continue
                    top = os.path.join(src_dir, rel.split(os.sep)[0])
                    if top not in entries:
                        entries.append(top)
                # 兜底：独立工作目录下的所有内容都属于这个任务
                if not entries and is_work_dir and os.path.isdir(src_dir):
                    for n in os.listdir(src_dir):
                        if not n.endswith(('.aria2', '.torrent')):
                            entries.append(os.path.join(src_dir, n))

            # 2) 逐个移动（跨磁盘时 shutil.move 会自动复制+删除）
            moved, errors = [], []
            for src in entries:
                if not os.path.exists(src):
                    continue
                dst = self._unique_dest(target, os.path.basename(src))
                try:
                    shutil.move(src, dst)
                    moved.append(dst)
                    logger.info(f"Moved {src} -> {dst}")
                except Exception as e:
                    errors.append(f"{os.path.basename(src)}: {e}")
                    logger.error(f"Failed to move {src} -> {dst}: {e}")

            if moved:
                task.final_paths = moved
            if errors:
                task.error_msg = "移动文件失败: " + "; ".join(errors)
                return False

            if moved:
                task.save_path = target
            elif entries:
                logger.warning(f"Task {task.id}: nothing to move, source files not found in {src_dir}")

            # 3) 清理该任务独立的临时工作目录（残留的 .aria2 控制文件等）
            if is_work_dir and os.path.isdir(src_dir):
                shutil.rmtree(src_dir, ignore_errors=True)
            return True
        except Exception as e:
            task.error_msg = f"移动文件失败: {e}"
            logger.error(f"Failed to move files for task {task.id}: {e}")
            return False

    def _on_bt_completed(self, task: DownloadTask, files: list):
        """BT/磁力任务下载完成：先停止做种，再把文件移动到指定目录，最后标记完成"""
        paths = [f.get('path', '') for f in (files or [])
                 if '[METADATA]' not in f.get('path', '')]

        task.metadata_received_at = 0
        task.error_msg = ""
        task.progress = 100.0
        if task.total_bytes > 0:
            task.downloaded_bytes = task.total_bytes
        task.speed = 0
        task.upload_speed = 0
        task.connections = 0
        task.completed_at = time.time()

        # 关键：停止做种。aria2 在“下载完成”后会继续 active 做种并占用文件，
        # 必须先把任务从 aria2 移除，才能停止上传、才能安全移动文件
        self._stop_aria2_task(task.aria2_gid)

        self._move_downloaded_files(task, paths)
        task.status = DownloadStatus.COMPLETED

    def _save_state(self):
        """Save tasks state to disk"""
        try:
            tasks_data = []
            for task in self.tasks.values():
                tasks_data.append({
                    'id': task.id,
                    'name': task.name,
                    'url': task.url,
                    'download_type': task.download_type,
                    'status': task.status.value,
                    'progress': task.progress,
                    'downloaded_bytes': task.downloaded_bytes,
                    'total_bytes': task.total_bytes,
                    'save_path': task.save_path,
                    'aria2_gid': task.aria2_gid,
                    'metadata_received_at': task.metadata_received_at,
                    'user_paused': task.user_paused,
                    'completed_at': task.completed_at,
                    'target_dir': task.target_dir,
                    'final_paths': task.final_paths,
                })
            with open(self._state_file, 'w') as f:
                json.dump({
                    'tasks': tasks_data,
                    'next_id': self.next_id
                }, f)
            logger.info(f"Saved {len(tasks_data)} tasks to state file")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _restore_tasks(self):
        """Restore tasks from saved state"""
        if not os.path.exists(self._state_file):
            logger.info("No saved state found, starting fresh")
            return

        try:
            with open(self._state_file, 'r') as f:
                data = json.load(f)

            self.next_id = data.get('next_id', 1)

            for task_data in data.get('tasks', []):
                save_path = task_data.get('save_path', self.save_path)
                # Convert relative paths to absolute paths
                if not os.path.isabs(save_path):
                    save_path = self._get_abs_path(save_path)
                task = DownloadTask(
                    id=task_data['id'],
                    name=task_data['name'],
                    url=task_data['url'],
                    download_type=task_data['download_type'],
                    save_path=save_path,
                )
                task.progress = task_data.get('progress', 0.0)
                task.downloaded_bytes = task_data.get('downloaded_bytes', 0)
                task.total_bytes = task_data.get('total_bytes', 0)
                task.aria2_gid = task_data.get('aria2_gid', '')
                task.metadata_received_at = task_data.get('metadata_received_at', 0)
                task.user_paused = task_data.get('user_paused', False)
                task.completed_at = task_data.get('completed_at', 0)
                task.final_paths = task_data.get('final_paths', [])
                target_dir = task_data.get('target_dir', '')
                if not target_dir:
                    # 旧版本保存的任务没有 target_dir：临时目录里的 -> 下载目录；已在指定目录里的 -> 原地不动
                    norm_save = os.path.normpath(save_path)
                    if norm_save == self._temp_path or norm_save.startswith(self._temp_path + os.sep):
                        target_dir = self._downloads_dir
                    else:
                        target_dir = save_path
                task.target_dir = target_dir

                # Initialize stop event for HTTP downloads
                task._stop_event = threading.Event()
                # If was paused, ensure stop event is set
                if task_data.get('status') == 'paused':
                    task._stop_event.set()

                # Restore status
                status_value = task_data.get('status', 'idle')
                try:
                    task.status = DownloadStatus(status_value)
                except:
                    task.status = DownloadStatus.IDLE

                self.tasks[task.id] = task

                # If task was running (active/downloading), try to resume it
                if task.status in (DownloadStatus.DOWNLOADING, DownloadStatus.IDLE):
                    # Check if aria2 still has this download
                    if task.aria2_gid:
                        status = self._aria2_get_status(task.aria2_gid)
                        if status and status.get('status') in ('active', 'waiting', 'paused'):
                            # Task is still running in aria2, keep its status
                            logger.info(f"Restored task {task.id}: {task.name} (aria2 status: {status.get('status')})")
                            continue
                        elif status and status.get('status') == 'complete':
                            # Download completed while we were shut down
                            self._on_bt_completed(task, status.get('files', []))
                            logger.info(f"Restored task {task.id}: {task.name} (completed while shut down)")
                            continue

                    # Task is not in aria2, try to restart it
                    if task.download_type in ('bt', 'magnet'):
                        logger.info(f"Restarting task {task.id}: {task.name}")
                        # Keep as IDLE (队列中), aria2 will handle actual status
                        self._restart_bt_task(task)
                    elif task.download_type == 'http':
                        logger.info(f"Restarting task {task.id}: {task.name}")
                        # Keep as IDLE, queue system will start it
                        self._start_next_waiting_task()
                else:
                    logger.info(f"Restored task {task.id}: {task.name} (status: {task.status.value})")

            logger.info(f"Restored {len(self.tasks)} tasks from state file")
        except Exception as e:
            logger.error(f"Failed to restore tasks: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _restart_bt_task(self, task: DownloadTask):
        """Re-add a BT/Magnet task to aria2"""
        options = {
            "dir": task.save_path,
            "bt-tracker": ",".join(self.PUBLIC_TRACKERS),
            "seed-time": "0",  # 下载完成后不做种
        }

        if task.download_type == 'magnet':
            # Append public trackers to magnet link if not already present
            magnet_url = task.url
            if not any(t in magnet_url for t in self.PUBLIC_TRACKERS):
                for tracker in self.PUBLIC_TRACKERS:
                    magnet_url += f"&tr={tracker}"
            gid = self._aria2_add_uri([magnet_url], options)
        elif task.download_type == 'bt':
            if task.url.startswith('data:'):
                data = task.url.split(',')[1]
                torrent_data = base64.b64decode(data)
                tmp_path = f"/tmp/{task.id}.torrent"
                with open(tmp_path, 'wb') as f:
                    f.write(torrent_data)
                gid = self._aria2_add_torrent(tmp_path, options)
            else:
                import urllib.request
                tmp_path = f"/tmp/{task.id}.torrent"
                urllib.request.urlretrieve(task.url, tmp_path)
                gid = self._aria2_add_torrent(tmp_path, options)

        if gid:
            task.aria2_gid = gid
            logger.info(f"Restarted BT/Magnet task {task.id} with new GID: {gid}")

    def _aria2_call(self, method: str, params: list) -> dict:
        """Call aria2 RPC API"""
        import urllib.request

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": time.time(),
            "method": method,
            "params": params
        }).encode()

        req = urllib.request.Request(
            f"http://localhost:{self._aria2_port}/jsonrpc",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 400:
                # Invalid GID or similar - this can happen for completed/removed downloads
                return None
            logger.error(f"Aria2 RPC HTTP error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Aria2 RPC error: {e}")
            return {"error": str(e)}

    def _aria2_add_uri(self, uris: List[str], options: dict = None) -> Optional[str]:
        """Add download via aria2"""
        params = [uris]
        if options:
            params.append(options)

        result = self._aria2_call("aria2.addUri", params)
        if "result" in result:
            return result["result"]
        logger.error(f"aria2.addUri failed: {result}")
        return None

    def _aria2_add_torrent(self, torrent_path: str, options: dict = None) -> Optional[str]:
        """Add torrent via aria2"""
        with open(torrent_path, "rb") as f:
            torrent_data = base64.b64encode(f.read()).decode()

        params = [torrent_data]
        if options:
            params.append(options)

        result = self._aria2_call("aria2.addTorrent", params)
        if "result" in result:
            return result["result"]
        logger.error(f"aria2.addTorrent failed: {result}")
        return None

    def _aria2_get_status(self, gid: str) -> Optional[dict]:
        """Get download status from aria2"""
        result = self._aria2_call(
            "aria2.tellStatus",
            [gid, ["status", "totalLength", "completedLength",
                   "downloadSpeed", "uploadSpeed", "connections",
                   "errorCode", "errorMessage", "files", "infoHash"]]
        )
        if result and "result" in result:
            return result["result"]
        return None

    def _aria2_get_active_downloads(self) -> List[dict]:
        """Get all active downloads from aria2"""
        result = self._aria2_call(
            "aria2.tellActive",
            [["status", "totalLength", "completedLength", "downloadSpeed",
              "connections", "errorCode", "errorMessage", "files", "infoHash", "gid", "seeder"]]
        )
        if "result" in result:
            return result["result"]
        return []

    def _find_gid_by_infohash(self, info_hash: str) -> Optional[str]:
        """Find aria2 GID by infoHash"""
        active_downloads = self._aria2_get_active_downloads()
        for download in active_downloads:
            if download.get("infoHash", "").lower() == info_hash.lower():
                return download.get("gid")
        # Also check waiting downloads
        result = self._aria2_call(
            "aria2.tellWaiting",
            [0, 100, [["status", "totalLength", "completedLength", "downloadSpeed",
                       "connections", "errorCode", "errorMessage", "files", "infoHash", "gid"]]]
        )
        if "result" in result:
            for download in result["result"]:
                if download.get("infoHash", "").lower() == info_hash.lower():
                    return download.get("gid")
        return None

    def _extract_infohash_from_magnet(self, magnet_url: str) -> Optional[str]:
        """Extract infoHash from magnet URL"""
        # Magnet format: magnet:?xt=urn:btih:<infohash>&dn=<name>&tr=...
        match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_url)
        if match:
            return match.group(1).lower()
        # Also try 32-char hash (base32 encoded)
        match = re.search(r'btih:([a-zA-Z2-7]{32})', magnet_url)
        if match:
            return match.group(1).lower()
        return None

    def _is_metadata_complete_only(self, status: dict) -> bool:
        """Check if status indicates metadata is complete but actual content is not downloaded yet"""
        if status.get("status") != "complete":
            return False
        files = status.get("files", [])
        if len(files) == 1 and "[METADATA]" in files[0].get("path", ""):
            return True
        return False

    def _aria2_pause(self, gid: str) -> bool:
        """Pause download"""
        result = self._aria2_call("aria2.pause", [gid])
        return "result" in result

    def _aria2_resume(self, gid: str) -> bool:
        """Resume download"""
        result = self._aria2_call("aria2.unpause", [gid])
        return result and "result" in result

    def _aria2_remove(self, gid: str) -> bool:
        """Remove download"""
        result = self._aria2_call("aria2.forceRemove", [gid])
        if result is None or "result" not in result:
            return False
        return True

    def _aria2_pause_all(self) -> bool:
        """Pause all downloads"""
        result = self._aria2_call("aria2.pauseAll", [])
        return "result" in result

    def _aria2_resume_all(self) -> bool:
        """Resume all downloads"""
        result = self._aria2_call("aria2.unpauseAll", [])
        return "result" in result

    def _aria2_change_max_concurrent(self, max_concurrent: int) -> bool:
        """Change aria2 max concurrent downloads setting"""
        result = self._aria2_call("aria2.changeGlobalOption", [{"max-concurrent-downloads": str(max_concurrent)}])
        return result and "result" in result

    def detect_type(self, url: str) -> tuple:
        """Detect download type from URL"""
        url = url.strip()

        # Thunder link
        if url.startswith('thunder://'):
            decoded = self._decode_thunder(url)
            return ('http', decoded)

        # Magnet link
        if url.startswith('magnet:?'):
            return ('magnet', url)

        # BT torrent file
        if url.endswith('.torrent') or url.startswith('data:'):
            return ('bt', url)

        # HTTP/HTTPS/FTP
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme in ('http', 'https', 'ftp'):
            return ('http', url)

        return ('unknown', url)

    def _count_active_downloads(self) -> int:
        """Count number of active (downloading) tasks"""
        count = 0
        for task in self.tasks.values():
            if task.status == DownloadStatus.DOWNLOADING:
                count += 1
        return count

    def _start_next_waiting_task(self):
        """Start the next waiting task if there's capacity"""
        if self._count_active_downloads() >= self._max_concurrent:
            return

        for task in self.tasks.values():
            if task.status == DownloadStatus.IDLE:
                if task.download_type == 'http':
                    self._start_http_download(task)
                    if self._count_active_downloads() >= self._max_concurrent:
                        return
                elif task.download_type in ('bt', 'magnet') and task.aria2_gid:
                    # Resume BT/Magnet task
                    if self._aria2_resume(task.aria2_gid):
                        task.status = DownloadStatus.DOWNLOADING
                        task.error_msg = ""
                        logger.info(f"Started waiting BT/Magnet task: {task.id}")
                        if self._count_active_downloads() >= self._max_concurrent:
                            return

    def _reap_seeding_slots(self):
        """清理仍在做种、占着 aria2 并发名额的“幽灵”任务。

        aria2 的 max-concurrent-downloads 会把做种中的任务也算进去，
        做种任务不退出，新任务就会一直“队列中”。这里只清理：
        已经完成的任务、或不属于任何任务的做种条目；正在下载的任务不会被动。
        """
        try:
            active = self._aria2_get_active_downloads()
        except Exception:
            return
        by_gid = {t.aria2_gid: t for t in self.tasks.values() if t.aria2_gid}
        by_hash = {}
        for t in self.tasks.values():
            if t.download_type == 'magnet':
                h = self._extract_infohash_from_magnet(t.url)
                if h:
                    by_hash[h] = t
        for d in active:
            total = int(d.get("totalLength", 0) or 0)
            done = int(d.get("completedLength", 0) or 0)
            seeding = str(d.get("seeder", "")).lower() == "true" or (total > 0 and done >= total)
            if not seeding:
                continue
            gid = d.get("gid")
            owner = by_gid.get(gid) or by_hash.get((d.get("infoHash") or "").lower())
            if owner is None or owner.status == DownloadStatus.COMPLETED:
                logger.info(f"Reaping seeding aria2 task {gid} (owner={owner.id if owner else None})")
                self._stop_aria2_task(gid)

    def _queue_reason(self) -> str:
        """给“排队中”的任务一个可读的原因"""
        try:
            n = len(self._aria2_get_active_downloads())
        except Exception:
            n = 0
        return f"排队中：下载引擎并发名额已满（{n}/{self._max_concurrent}），等待空位"

    def _decode_thunder(self, thunder_url: str) -> str:
        """Decode thunder:// URL to original URL"""
        if not thunder_url.startswith('thunder://'):
            return thunder_url
        encoded = thunder_url[10:].rstrip('/')
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            return decoded.strip('EX')
        except:
            return thunder_url

    def add_task(self, url: str, name: str = "", save_path: str = "") -> DownloadTask:
        """Add a new download task"""
        download_type, real_url = self.detect_type(url)

        if download_type == 'unknown':
            raise ValueError(f"Unknown download type: {url}")

        # Check for duplicate URL
        if download_type == 'magnet':
            # For magnet, check by infoHash
            info_hash = self._extract_infohash_from_magnet(real_url)
            if info_hash:
                for task in self.tasks.values():
                    if task.download_type == 'magnet':
                        task_info_hash = self._extract_infohash_from_magnet(task.url)
                        if task_info_hash and task_info_hash == info_hash:
                            raise ValueError("下载任务已存在")
        else:
            # For other types, check by exact URL
            for task in self.tasks.values():
                if task.url == real_url:
                    raise ValueError("下载任务已存在")

        task_id = f"task_{self.next_id}"
        self.next_id += 1

        # Extract name from URL if not provided
        if not name:
            if download_type == 'magnet':
                parsed = urllib.parse.urlparse(real_url)
                params = urllib.parse.parse_qs(parsed.query)
                if 'dn' in params:
                    name = params['dn'][0]
                else:
                    name = "Magnet Download"
            else:
                parsed = urllib.parse.urlparse(real_url)
                name = os.path.basename(parsed.path) or "Untitled"

        # 最终保存目录：留空 = 下载目录；填写 = 下载目录下的子目录，不存在则新建
        try:
            target_dir = self._resolve_target_dir(save_path)
        except ValueError:
            self.next_id -= 1
            raise
        os.makedirs(target_dir, exist_ok=True)

        # 下载过程中使用该任务独立的临时工作目录，完成后再移动到 target_dir
        work_dir = os.path.join(self._temp_path, task_id)
        os.makedirs(work_dir, exist_ok=True)

        task = DownloadTask(
            id=task_id,
            name=name,
            url=real_url,
            download_type=download_type,
            save_path=work_dir,
            target_dir=target_dir,
        )
        save_path = target_dir

        self.tasks[task_id] = task
        logger.info(f"Added task: {task_id} ({download_type}) - {name} -> {save_path}")

        # Start download based on type, respecting concurrent limit
        if download_type in ('bt', 'magnet'):
            task.status = DownloadStatus.IDLE
            task.error_msg = "等待中..."
            self._start_bt_download(task)
        elif download_type == 'http':
            # HTTP downloads always start as IDLE, let queue system start them
            task.status = DownloadStatus.IDLE
            task.error_msg = "等待中..."
            logger.info(f"Task {task_id} added as HTTP, status: IDLE")
            # Try to start it immediately if there's capacity
            self._start_next_waiting_task()

        return task

    # Public tracker servers for BT downloads
    PUBLIC_TRACKERS = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.cyberia.space:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.torrentbox.dev:32020/announce",
        "udp://tracker.moeking.me:20615/announce",
        "udp://tracker.quk.cc:2710/announce",
        "http://tracker.opentrackr.org:1337/announce",
        "https://tracker.opentrackr.org:443/announce",
    ]

    def _start_bt_download(self, task: DownloadTask):
        """Start BT/Magnet download via aria2"""
        options = {
            "dir": task.save_path,
            "bt-tracker": ",".join(self.PUBLIC_TRACKERS),
            "seed-time": "0",  # 下载完成后不做种
        }

        logger.info(f"Starting BT download: {task.name}")
        logger.info(f"Magnet URL: {task.url}")

        if task.download_type == 'magnet':
            # Append public trackers to magnet link if not already present
            magnet_url = task.url
            if not any(t in magnet_url for t in self.PUBLIC_TRACKERS):
                for tracker in self.PUBLIC_TRACKERS:
                    magnet_url += f"&tr={tracker}"
            gid = self._aria2_add_uri([magnet_url], options)
        elif task.download_type == 'bt':
            # Handle .torrent URL or data URL
            if task.url.startswith('data:'):
                # Decode base64 torrent
                data = task.url.split(',')[1]
                torrent_data = base64.b64decode(data)
                tmp_path = f"/tmp/{task.id}.torrent"
                with open(tmp_path, 'wb') as f:
                    f.write(torrent_data)
                gid = self._aria2_add_torrent(tmp_path, options)
            else:
                # Download .torrent file first
                import urllib.request
                tmp_path = f"/tmp/{task.id}.torrent"
                urllib.request.urlretrieve(task.url, tmp_path)
                gid = self._aria2_add_torrent(tmp_path, options)
        else:
            gid = None

        if gid:
            task.aria2_gid = gid
            # Keep IDLE status, will change to DOWNLOADING when aria2 starts downloading actual content
            logger.info(f"Added BT/Magnet to aria2: {task.name} (GID: {gid}), status: IDLE")
        else:
            task.status = DownloadStatus.FAILED
            task.error_msg = "Failed to start download"

    def _start_http_download(self, task: DownloadTask):
        """Start HTTP/FTP download in a thread"""
        task._stop_event = threading.Event()
        thread = threading.Thread(target=self._http_download_worker, args=(task,))
        thread.daemon = True
        thread.start()

    def _http_download_worker(self, task: DownloadTask, resume_offset=0):
        """HTTP download worker thread"""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        task.status = DownloadStatus.DOWNLOADING

        try:
            # Setup retry strategy
            session = requests.Session()
            retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            # Prepare headers for resume
            headers = {}
            if resume_offset > 0:
                headers['Range'] = f'bytes={resume_offset}-'

            with session.get(task.url, stream=True, timeout=30, headers=headers) as response:
                # Handle resume - if 416 (Range not satisfiable), start from beginning
                if resume_offset > 0 and response.status_code == 416:
                    resume_offset = 0
                    headers = {}
                    response = session.get(task.url, stream=True, timeout=30, headers=headers)

                response.raise_for_status()
                total = int(response.headers.get('Content-Length', 0))
                if resume_offset > 0:
                    total += resume_offset
                task.total_bytes = total

                # Determine filename
                filename = task.name
                if not filename or filename == "Untitled":
                    content_disp = response.headers.get('Content-Disposition', '')
                    match = re.search(r'filename="?([^"]+)"?', content_disp)
                    if match:
                        filename = match.group(1)
                    else:
                        filename = os.path.basename(task.url) or "download"

                filepath = os.path.join(task.save_path, filename)
                task.name = filename

                # Use append mode for resume
                mode = 'ab' if resume_offset > 0 else 'wb'
                downloaded = resume_offset
                start_time = time.time()
                last_speed_time = start_time
                last_speed_bytes = 0

                os.makedirs(task.save_path, exist_ok=True)
                with open(filepath, mode) as f:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        # Check if pause was requested
                        if task._stop_event.is_set():
                            logger.info(f"HTTP download paused: {task.name} at {downloaded} bytes")
                            task.status = DownloadStatus.PAUSED
                            task.error_msg = ""
                            return

                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        task.downloaded_bytes = downloaded

                        if total > 0:
                            task.progress = (downloaded / total) * 100

                        # Calculate speed
                        now = time.time()
                        if now - last_speed_time >= 1.0:
                            elapsed = now - last_speed_time
                            speed = int((downloaded - last_speed_bytes) / elapsed)
                            task.speed = speed
                            last_speed_time = now
                            last_speed_bytes = downloaded

                task.progress = 100.0
                task.speed = 0
                task.error_msg = ""
                task.completed_at = time.time()
                self._move_downloaded_files(task)   # 移动到指定目录
                task.status = DownloadStatus.COMPLETED
                logger.info(f"Download completed: {task.name}")

        except Exception as e:
            logger.error(f"HTTP download error: {e}")
            task.status = DownloadStatus.FAILED
            task.error_msg = str(e)
            task.error_msg = str(e)

    def pause_task(self, task_id: str) -> bool:
        """Pause a download task"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.user_paused = True  # Mark as user paused to prevent auto-recovery

        if task.download_type in ('bt', 'magnet') and task.aria2_gid:
            if self._aria2_pause(task.aria2_gid):
                task.status = DownloadStatus.PAUSED
                return True

        if task.download_type == 'http':
            if task.status == DownloadStatus.DOWNLOADING:
                # Signal HTTP download thread to stop gracefully
                task._stop_event.set()
            # For both IDLE and DOWNLOADING, mark as PAUSED
            task.status = DownloadStatus.PAUSED
            task.error_msg = ""
            return True

        return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a download task"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.user_paused = False  # Clear the user paused flag

        if task.download_type in ('bt', 'magnet') and task.aria2_gid:
            # Check if we can resume (under concurrent limit)
            if self._count_active_downloads() >= self._max_concurrent:
                # At limit - set to idle/queued instead of downloading
                task.status = DownloadStatus.IDLE
                task.error_msg = "等待中...（队列）"
                logger.info(f"Task {task_id} queued on resume, at concurrent limit")
                return True
            if self._aria2_resume(task.aria2_gid):
                task.status = DownloadStatus.DOWNLOADING
                task.error_msg = ""
                return True

        if task.download_type == 'http':
            # Reset stop event
            task._stop_event.clear()
            # If was PAUSED with downloaded bytes, resume from where we left off
            # Otherwise just start fresh
            resume_offset = task.downloaded_bytes if task.status == DownloadStatus.PAUSED and task.downloaded_bytes > 0 else 0
            thread = threading.Thread(target=self._http_download_worker, args=(task, resume_offset))
            thread.daemon = True
            thread.start()
            task.status = DownloadStatus.DOWNLOADING
            task.error_msg = ""
            return True

        return False

    def remove_task(self, task_id: str, delete_files: bool = True) -> bool:
        """Remove a download task"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        try:
            # Collect files to delete before removing from aria2
            files_to_delete = []
            if delete_files:
                files_to_delete = self._collect_files_to_delete(task)

            # Remove from aria2 (may fail for completed/stale GIDs)
            if task.download_type in ('bt', 'magnet') and task.aria2_gid:
                try:
                    self._aria2_remove(task.aria2_gid)
                except Exception as e:
                    logger.warning(f"aria2 remove failed for {task_id}: {e}")

            # Delete downloaded files if requested
            if delete_files:
                self._delete_files_list(files_to_delete)
                if self._is_task_work_dir(task):
                    shutil.rmtree(task.save_path, ignore_errors=True)

            del self.tasks[task_id]
            return True
        except Exception as e:
            logger.error(f"Remove error: {e}")
            return False
            return False

    def clear_completed(self) -> int:
        """Clear all completed tasks without deleting files. Returns count of cleared tasks."""
        cleared = 0
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if task.status == DownloadStatus.COMPLETED:
                tasks_to_remove.append(task_id)
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            cleared += 1
        return cleared

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[DownloadTask]:
        """List all tasks"""
        return list(self.tasks.values())

    def update_task_progress(self, task: DownloadTask):
        """Update task progress from aria2"""
        if task.download_type not in ('bt', 'magnet'):
            return

        # Skip completed tasks - no need to query aria2
        if task.status == DownloadStatus.COMPLETED:
            return

        # If user manually paused, don't override the status
        if task.user_paused:
            return

        if not task.aria2_gid:
            return

        # Try to get status with stored GID first
        status = self._aria2_get_status(task.aria2_gid)

        # If status is None or GID not found, or metadata complete but content elsewhere, find correct GID
        gid_switched = False
        if not status or self._is_metadata_complete_only(status):
            if task.download_type == 'magnet':
                info_hash = self._extract_infohash_from_magnet(task.url)
                if info_hash:
                    correct_gid = self._find_gid_by_infohash(info_hash)
                    if correct_gid and correct_gid != task.aria2_gid:
                        task.aria2_gid = correct_gid
                        status = self._aria2_get_status(correct_gid)
                        gid_switched = True

        if not status:
            logger.warning(f"Failed to get status for task {task.id}, GID: {task.aria2_gid}")
            return

        # After GID switch, re-check status to get proper files info
        if gid_switched:
            status = self._aria2_get_status(task.aria2_gid)

        if not status:
            logger.warning(f"Failed to get status for task {task.id}, GID: {task.aria2_gid}")
            return

        try:
            # Map aria2 status to our status
            aria2_status = status.get("status", "")

            # Get files info to check if actual content is downloaded
            files = status.get("files", [])

            # Check if only metadata file exists (not real content)
            file_paths = [f.get("path", "") for f in files]
            is_metadata_only = len(files) == 1 and "[METADATA]" in file_paths[0]

            # Check if real content files exist (not metadata)
            has_actual_content = any(
                "[METADATA]" not in f.get("path", "") and int(f.get("length", 0)) > 0
                for f in files
            )

            # Update common fields
            task.total_bytes = int(status.get("totalLength", 0))
            task.downloaded_bytes = int(status.get("completedLength", 0))
            task.speed = int(status.get("downloadSpeed", 0))
            task.upload_speed = int(status.get("uploadSpeed", 0))
            task.connections = int(status.get("connections", 0))

            if aria2_status == "active":
                if is_metadata_only and not has_actual_content:
                    # Metadata received, waiting for peers to start downloading content
                    if task.metadata_received_at == 0:
                        task.metadata_received_at = time.time()
                    elapsed = time.time() - task.metadata_received_at
                    task.status = DownloadStatus.IDLE
                    task.error_msg = f"正在获取资源信息...（{int(elapsed)}秒）"
                    task.progress = 0
                    task.total_bytes = 0
                    task.downloaded_bytes = 0
                else:
                    # Real content is being downloaded
                    task.metadata_received_at = 0
                    task.error_msg = ""
                    if task.total_bytes > 0:
                        task.progress = (task.downloaded_bytes / task.total_bytes) * 100
                        # Check if download is actually complete
                        if task.downloaded_bytes >= task.total_bytes:
                            # 下载完成：停止做种 -> 移动到指定目录 -> 标记完成
                            self._on_bt_completed(task, files)
                        else:
                            task.status = DownloadStatus.DOWNLOADING

            elif aria2_status == "paused":
                task.status = DownloadStatus.PAUSED
                task.metadata_received_at = 0

            elif aria2_status == "waiting":
                task.status = DownloadStatus.IDLE
                task.error_msg = self._queue_reason()

            elif aria2_status == "complete":
                if is_metadata_only and not has_actual_content:
                    # Metadata is complete, still waiting for content download
                    if task.metadata_received_at == 0:
                        task.metadata_received_at = time.time()
                    elapsed = time.time() - task.metadata_received_at
                    task.status = DownloadStatus.IDLE
                    task.error_msg = f"正在获取资源信息...（{int(elapsed)}秒）"
                    task.progress = 0
                    task.total_bytes = 0
                    task.downloaded_bytes = 0
                else:
                    # Real content has been downloaded
                    self._on_bt_completed(task, files)

            elif aria2_status == "error":
                task.metadata_received_at = 0
                error_code = status.get("errorCode", "")
                error_msg = status.get("errorMessage", "Unknown error")
                # Only mark as failed for certain errors, not for resource not found
                if error_code == "12":
                    # Resource already exists - this is ok, don't fail
                    task.status = DownloadStatus.IDLE
                    task.error_msg = "资源已在下载列表中"
                elif error_msg:
                    task.status = DownloadStatus.IDLE
                    task.error_msg = f"下载暂停: {error_msg}"
                else:
                    task.status = DownloadStatus.IDLE
                    task.error_msg = f"下载暂停（错误码: {error_code}）"

            elif aria2_status == "stopped":
                # Stopped - don't mark as failed, just show as paused/waiting
                task.metadata_received_at = 0
                if has_actual_content and not is_metadata_only:
                    self._on_bt_completed(task, files)
                else:
                    task.status = DownloadStatus.IDLE
                    task.error_msg = "等待下载..."

            # Only update error message if not already set and no error occurred
            if not task.error_msg and status.get("errorMessage") and aria2_status == "active":
                task.error_msg = status["errorMessage"]
            if files and not task.name:
                task.name = os.path.basename(files[0]["path"])

        except Exception as e:
            logger.debug(f"Progress update error: {e}")

    def pause_all(self) -> bool:
        """Pause all downloads"""
        for task in self.tasks.values():
            if task.status == DownloadStatus.DOWNLOADING:
                self.pause_task(task.id)
        return True

    def resume_all(self) -> bool:
        """Resume all downloads"""
        for task in self.tasks.values():
            if task.status == DownloadStatus.PAUSED:
                self.resume_task(task.id)
        return True

    def get_stats(self) -> dict:
        """Get download statistics"""
        result = self._aria2_call("aria2.getGlobalStat", [])
        if "result" in result:
            return result["result"]
        return {}

    def shutdown(self):
        """Shutdown aria2"""
        self._save_state()
        if self._aria2_session:
            self._aria2_session.terminate()

# =============================================================================
# Global instance
# =============================================================================

manager = DownloadManager()

# Progress update thread
_save_counter = 0
def progress_updater():
    """Background thread to update task progress"""
    global _save_counter
    while True:
        try:
            for task in manager.list_tasks():
                manager.update_task_progress(task)
            # 清理占着并发名额的做种任务，再尝试启动排队任务
            manager._reap_seeding_slots()
            manager._start_next_waiting_task()
            # Save state every 30 seconds
            _save_counter += 1
            if _save_counter >= 30:
                manager._save_state()
                _save_counter = 0
        except Exception as e:
            logger.debug(f"Progress update error: {e}")
        time.sleep(1.0)

progress_thread = threading.Thread(target=progress_updater, daemon=True)
progress_thread.start()

# =============================================================================
# API Routes
# =============================================================================

@app.route('/api/tasks', methods=['POST'])
def add_task():
    """Add a new download task"""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    try:
        task = manager.add_task(
            url=data['url'],
            name=data.get('name', ''),
            save_path=data.get('savePath', '')
        )
        return jsonify(_task_to_dict(task)), 200
    except Exception as e:
        logger.error(f"Add task error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """List all tasks"""
    tasks = [_task_to_dict(t) for t in manager.list_tasks()]
    return jsonify({'tasks': tasks, 'total': len(tasks)})

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get task by ID"""
    task = manager.get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(_task_to_dict(task))

@app.route('/api/tasks/<task_id>/pause', methods=['POST'])
def pause_task(task_id):
    """Pause a task"""
    if manager.pause_task(task_id):
        return jsonify({'message': 'paused'})
    return jsonify({'error': 'Failed to pause'}), 500

@app.route('/api/tasks/<task_id>/resume', methods=['POST'])
def resume_task(task_id):
    """Resume a task"""
    if manager.resume_task(task_id):
        return jsonify({'message': 'resumed'})
    return jsonify({'error': 'Failed to resume'}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def remove_task(task_id):
    """Remove a task"""
    delete_files = request.args.get('deleteFiles', '').lower() == 'true'
    if manager.remove_task(task_id, delete_files=delete_files):
        return jsonify({'message': 'removed'})
    return jsonify({'error': 'Failed to remove'}), 500

@app.route('/api/tasks/pause-all', methods=['POST'])
def pause_all():
    """Pause all tasks"""
    manager.pause_all()
    return jsonify({'message': 'all paused'})

@app.route('/api/tasks/resume-all', methods=['POST'])
def resume_all():
    """Resume all tasks"""
    manager.resume_all()
    return jsonify({'message': 'all resumed'})

@app.route('/api/tasks/clear-completed', methods=['POST'])
def clear_completed():
    """Clear all completed task records without deleting files"""
    count = manager.clear_completed()
    return jsonify({'message': f'cleared {count} completed tasks', 'count': count})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get download statistics"""
    return jsonify(manager.get_stats())

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get settings"""
    return jsonify(manager.get_settings())

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    """Update settings"""
    data = request.get_json()
    if data:
        manager.update_settings(data)
    return jsonify({'message': 'settings updated'})

# =============================================================================
# Share Routes
# =============================================================================

@app.route('/api/share/status', methods=['GET'])
def get_share_status():
    """Get share status"""
    return jsonify(manager.get_share_status())

@app.route('/api/share/enable', methods=['POST'])
def enable_share():
    """Enable file sharing"""
    result = manager.enable_share()
    if result.get('success'):
        return jsonify({'message': 'Share enabled'})
    return jsonify({'error': result.get('error', 'Failed to enable share')}), 500

@app.route('/api/share/disable', methods=['POST'])
def disable_share():
    """Disable file sharing"""
    result = manager.disable_share()
    if result.get('success'):
        return jsonify({'message': 'Share disabled'})
    return jsonify({'error': result.get('error', 'Failed to disable share')}), 500

# =============================================================================
# Auth Routes
# =============================================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login with password"""
    data = request.get_json()
    if not data or 'password' not in data:
        return jsonify({'error': 'password is required'}), 400

    user = manager.verify_login(data['password'])
    if user:
        # Generate JWT token
        token = create_token()
        return jsonify({
            'success': True,
            'user': user,
            'token': token
        })
    return jsonify({'success': False, 'error': '密码错误'}), 401

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check auth status"""
    # This route is exempt from session check
    must_change = manager._settings.get('mustChangePassword', False)
    return jsonify({
        'authenticated': True,
        'mustChangePassword': must_change
    })

@app.route('/api/auth/change-password', methods=['POST'])
def change_password():
    """Change password with old password verification"""
    data = request.get_json()
    if not data or 'oldPassword' not in data or 'newPassword' not in data:
        return jsonify({'error': 'oldPassword and newPassword are required'}), 400

    result = manager.change_password(data['oldPassword'], data['newPassword'])
    if result.get('success'):
        return jsonify({'success': True, 'message': '密码修改成功'})
    return jsonify({'success': False, 'error': result.get('error', '修改失败')}), 400

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout and invalidate session"""
    token = request.headers.get('X-Session-Token', '')
    if token in _sessions:
        del _sessions[token]
    return jsonify({'success': True})

# =============================================================================
# File Management Routes
# =============================================================================

def _get_save_dir():
    """Get the actual save directory path"""
    path = manager._downloads_dir
    logger.info(f"_get_save_dir called, returning: {path}")
    return path

@app.route('/api/files', methods=['GET'])
def list_files():
    """List files and directories in a path"""
    rel_path = request.args.get('path', '').lstrip('/')
    sort_order = request.args.get('sort', 'name')  # 'name', 'date_asc', 'date_desc'
    base_dir = _get_save_dir()

    if rel_path:
        target_dir = os.path.join(base_dir, rel_path)
    else:
        target_dir = base_dir

    # Security check - ensure path is within base_dir
    if not target_dir.startswith(base_dir):
        return jsonify({'error': 'Invalid path'}), 400

    if not os.path.exists(target_dir):
        return jsonify({'error': 'Path not found'}), 404

    items = []
    try:
        for name in os.listdir(target_dir):
            # Skip hidden files (starting with .)
            if name.startswith('.'):
                continue
            item_path = os.path.join(target_dir, name)
            try:
                stat = os.stat(item_path)
            except FileNotFoundError:
                continue
            is_dir = os.path.isdir(item_path)

            items.append({
                'name': name,
                'path': os.path.relpath(item_path, base_dir),
                'isDir': is_dir,
                'size': stat.st_size if not is_dir else 0,
                'modifiedAt': stat.st_mtime,
            })

        # Sort items together by selected order
        if sort_order == 'date_desc':
            items.sort(key=lambda x: x['modifiedAt'], reverse=True)
        elif sort_order == 'date_asc':
            items.sort(key=lambda x: x['modifiedAt'])
        else:  # sort by name
            items.sort(key=lambda x: x['name'].lower())
    except Exception as e:
        logger.error(f"List files error: {e}")
        return jsonify({'error': str(e)}), 500

    return jsonify({'items': items, 'basePath': rel_path})

@app.route('/api/files/mkdir', methods=['POST'])
def create_directory():
    """Create a new directory"""
    data = request.get_json()
    if not data or 'path' not in data or 'name' not in data:
        return jsonify({'error': 'path and name are required'}), 400

    rel_path = data.get('path', '').lstrip('/')
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Name cannot be empty'}), 400

    base_dir = _get_save_dir()
    if rel_path:
        target_dir = os.path.join(base_dir, rel_path)
    else:
        target_dir = base_dir

    # Security check
    if not target_dir.startswith(base_dir):
        return jsonify({'error': 'Invalid path'}), 400

    new_dir = os.path.join(target_dir, name)
    try:
        os.makedirs(new_dir, exist_ok=False)
        return jsonify({'message': 'Directory created', 'path': os.path.relpath(new_dir, base_dir)})
    except FileExistsError:
        return jsonify({'error': 'Directory already exists'}), 400
    except Exception as e:
        logger.error(f"Create directory error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/rename', methods=['POST'])
def rename_item():
    """Rename a file or directory"""
    data = request.get_json()
    if not data or 'path' not in data or 'newName' not in data:
        return jsonify({'error': 'path and newName are required'}), 400

    rel_path = data.get('path', '').lstrip('/')
    new_name = data.get('newName', '').strip()

    if not new_name:
        return jsonify({'error': 'Name cannot be empty'}), 400

    base_dir = _get_save_dir()
    old_path = os.path.join(base_dir, rel_path)

    # Security check
    if not old_path.startswith(base_dir):
        return jsonify({'error': 'Invalid path'}), 400

    new_path = os.path.join(os.path.dirname(old_path), new_name)

    try:
        os.rename(old_path, new_path)
        return jsonify({'message': 'Renamed successfully', 'newPath': os.path.relpath(new_path, base_dir)})
    except Exception as e:
        logger.error(f"Rename error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/delete', methods=['POST'])
def delete_items():
    """Delete files or directories"""
    data = request.get_json()
    if not data or 'paths' not in data:
        return jsonify({'error': 'paths is required'}), 400

    paths = data.get('paths', [])
    if not paths:
        return jsonify({'error': 'No paths provided'}), 400

    base_dir = _get_save_dir()
    deleted = []
    errors = []

    for rel_path in paths:
        rel_path = rel_path.lstrip('/')
        target_path = os.path.join(base_dir, rel_path)

        # Security check
        if not target_path.startswith(base_dir):
            errors.append({'path': rel_path, 'error': 'Invalid path'})
            continue

        try:
            import shutil
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            deleted.append(rel_path)
        except Exception as e:
            logger.error(f"Delete error for {rel_path}: {e}")
            errors.append({'path': rel_path, 'error': str(e)})

    return jsonify({'deleted': deleted, 'errors': errors})

@app.route('/api/files/move', methods=['POST'])
def move_items():
    """Move files or directories"""
    data = request.get_json()
    if not data or 'paths' not in data or 'targetPath' not in data:
        return jsonify({'error': 'paths and targetPath are required'}), 400

    paths = data.get('paths', [])
    target_rel = data.get('targetPath', '').lstrip('/')

    if not paths:
        return jsonify({'error': 'No paths provided'}), 400

    base_dir = _get_save_dir()
    target_dir = os.path.join(base_dir, target_rel) if target_rel else base_dir

    # Security check
    if not target_dir.startswith(base_dir):
        return jsonify({'error': 'Invalid target path'}), 400

    if not os.path.exists(target_dir):
        return jsonify({'error': 'Target directory does not exist'}), 400

    moved = []
    errors = []

    for rel_path in paths:
        rel_path = rel_path.lstrip('/')
        src_path = os.path.join(base_dir, rel_path)
        new_path = os.path.join(target_dir, os.path.basename(src_path))

        # Security check
        if not src_path.startswith(base_dir):
            errors.append({'path': rel_path, 'error': 'Invalid path'})
            continue

        # Check if target already exists
        if os.path.exists(new_path):
            errors.append({'path': rel_path, 'error': 'Target already exists'})
            continue

        try:
            import shutil
            shutil.move(src_path, new_path)
            moved.append({'from': rel_path, 'to': os.path.relpath(new_path, base_dir)})
        except Exception as e:
            logger.error(f"Move error for {rel_path}: {e}")
            errors.append({'path': rel_path, 'error': str(e)})

    return jsonify({'moved': moved, 'errors': errors})

@app.route('/api/files/copy', methods=['POST'])
def copy_items():
    """Copy files to a target directory"""
    data = request.get_json()
    if not data or 'paths' not in data:
        return jsonify({'error': 'paths is required'}), 400

    paths = data.get('paths', [])
    target_rel = data.get('targetPath', '').lstrip('/')  # optional target directory
    if not paths:
        return jsonify({'error': 'No paths provided'}), 400

    base_dir = _get_save_dir()
    target_dir = os.path.join(base_dir, target_rel) if target_rel else base_dir

    # Security check
    if not target_dir.startswith(base_dir):
        return jsonify({'error': 'Invalid target path'}), 400

    copied = []
    errors = []

    for rel_path in paths:
        rel_path = rel_path.lstrip('/')
        src_path = os.path.join(base_dir, rel_path)

        # Security check
        if not src_path.startswith(base_dir):
            errors.append({'path': rel_path, 'error': 'Invalid path'})
            continue

        # Cannot copy directory
        if os.path.isdir(src_path):
            errors.append({'path': rel_path, 'error': 'Cannot copy directory'})
            continue

        # Generate new filename: file.ext -> file (1).ext in target dir
        src_name = os.path.basename(src_path)
        name, ext = os.path.splitext(src_name)
        counter = 1
        new_name = f"{name} (1){ext}"
        new_path = os.path.join(target_dir, new_name)
        while os.path.exists(new_path):
            counter += 1
            new_name = f"{name} ({counter}){ext}"
            new_path = os.path.join(target_dir, new_name)

        try:
            import shutil
            shutil.copy2(src_path, new_path)
            copied.append({'from': rel_path, 'to': os.path.relpath(new_path, base_dir)})
        except Exception as e:
            logger.error(f"Copy error for {rel_path}: {e}")
            errors.append({'path': rel_path, 'error': str(e)})

    return jsonify({'copied': copied, 'errors': errors})

@app.route('/api/files/download', methods=['GET'])
def download_file():
    """Download a file"""
    rel_path = request.args.get('path', '').lstrip('/')
    if not rel_path:
        return jsonify({'error': 'path is required'}), 400

    base_dir = _get_save_dir()
    file_path = os.path.join(base_dir, rel_path)

    # Security check
    if not file_path.startswith(base_dir):
        return jsonify({'error': 'Invalid path'}), 400

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    if os.path.isdir(file_path):
        return jsonify({'error': 'Cannot download directory'}), 400

    filename = os.path.basename(file_path)
    response = send_file(file_path, as_attachment=True)
    encoded_filename = urllib.parse.quote(filename)
    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
    return response

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({'status': 'ok'})

@app.route('/api/debug/paths', methods=['GET'])
def debug_paths():
    """Debug endpoint to check path configuration"""
    return jsonify({
        'app_file': os.path.abspath(__file__),
        'backend_dir': os.path.dirname(os.path.abspath(__file__)),
        'project_root': os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'DOWNLOADS_DIR': DOWNLOADS_DIR,
        '_downloads_dir': manager._downloads_dir,
        '_temp_path': manager._temp_path,
        'save_path': manager.save_path,
        '_data_dir': manager._data_dir,
        'cwd': os.getcwd(),
        'env_APP_HOME': os.environ.get('APP_HOME', 'not set'),
    })

def _task_to_dict(task: DownloadTask) -> dict:
    """Convert task to dictionary"""
    return {
        'id': task.id,
        'name': task.name,
        'url': task.url,
        'type': task.download_type,
        'savePath': task.save_path,
        'targetDir': task.target_dir,
        'status': task.status.value,
        'progress': task.progress,
        'downloaded': task.downloaded_bytes,
        'totalSize': task.total_bytes,
        'speed': task.speed,
        'uploadSpeed': task.upload_speed,
        'connections': task.connections,
        'errorMsg': task.error_msg,
        'createdAt': task.created_at,
        'updatedAt': task.completed_at if task.status == DownloadStatus.COMPLETED else time.time(),
        'completedAt': task.completed_at,
        'aria2Gid': task.aria2_gid,
    }

if __name__ == '__main__':
    import signal

    # Register signal handlers BEFORE Flask starts
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping services...")
        # Flask will raise SystemExit when we call shutdown
        manager.shutdown()
        logger.info("Shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("EasyNAS server starting...")
    logger.info("Press Ctrl+C to stop")

    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
