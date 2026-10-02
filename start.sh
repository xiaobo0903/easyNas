#!/bin/bash
set -e

echo "Starting EasyNAS..."

# Function to handle shutdown
shutdown() {
    echo "Shutting down EasyNAS..."
    pkill -f "python backend-py/app.py" || true
    pkill nginx || true
    pkill smbd || true
    pkill nmbd || true
    exit 0
}

trap shutdown SIGTERM SIGINT

# Generate Samba configuration if not exists
if [ ! -f /app/data/smb.conf ]; then
    echo "Generating Samba configuration..."
    cat > /app/data/smb.conf << 'EOF'
[global]
   netbios name = easynas
   workgroup = WORKGROUP
   server string = EasyNAS Samba Server
   server role = standalone server
   map to guest = Bad Password
   dns proxy = No
   log file = /var/log/samba/log.%m
   max log size = 1000
   socket options = TCP_NODELAY IPTOS_LOWDELAY
   encrypt passwords = yes
   smb encrypt = desired
   read raw = yes
   write raw = yes
   use sendfile = yes
   aio read size = 16384
   aio write size = 16384

[downloads]
   path = /app/downloads
   comment = EasyNAS Download Share
   browseable = Yes
   read only = No
   create mask = 0664
   directory mask = 0775
   guest only = Yes
   guest ok = Yes
   force user = root
EOF
fi

# Set permissions on downloads directory
chmod -R 777 /app/downloads

# Start nginx (frontend + reverse proxy)
echo "Starting nginx..."
nginx -c /etc/nginx/nginx.conf

# Start Python backend with virtual environment
echo "Starting backend..."
cd /app
/app/backend-py/.venv/bin/python backend-py/app.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start Samba
echo "Starting Samba..."
smbd -s /app/data/smb.conf -F &
nmbd -s /app/data/smb.conf -F &

# Check if services are running
echo ""
echo "=========================================="
echo "EasyNAS Services Status"
echo "=========================================="
echo ""

if curl -sf http://localhost:8080/api/health > /dev/null; then
    echo "  [OK] Backend API (port 8080)"
else
    echo "  [WARN] Backend API may not be ready"
fi

if pgrep -x nginx > /dev/null; then
    echo "  [OK] Nginx (port 80)"
else
    echo "  [WARN] Nginx not running"
fi

if pgrep -x smbd > /dev/null; then
    echo "  [OK] Samba (port 445)"
else
    echo "  [WARN] Samba not running"
fi

echo ""
echo "EasyNAS started successfully!"
echo "  Web UI:      http://localhost"
echo "  API:         http://localhost:8080"
echo "  SMB Share:   \\\\localhost\\downloads (guest access)"
echo ""

# Wait for any process to exit
wait $BACKEND_PID
