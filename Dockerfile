FROM python:3.12-slim

LABEL maintainer="EasyNAS"
LABEL description="EasyNAS - All-in-One Download Manager"

# Use Tsinghua mirror for apt
RUN sed -i 's|http://deb.debian.org|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|http://security.debian.org|http://mirrors.tuna.tsinghua.edu.cn/security|g' /etc/apt/sources.list.d/debian.sources

# Install system dependencies, Node.js and Samba
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    aria2 \
    nginx \
    samba \
    samba-common-bin \
    smbclient \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x from Tsinghua mirror (Vite requires Node.js 22.12+)
RUN curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/v22.12.0/node-v22.12.0-linux-x64.tar.gz | tar -xz -C /usr/local --strip-components=1 \
    && rm -rf /tmp/*

# Set working directory
WORKDIR /app

# Copy entire project to /app, keeping directory structure
COPY . /app/

# Create Python virtual environment in backend-py/.venv
RUN python3 -m venv /app/backend-py/.venv

# Install Python dependencies using the venv
RUN /app/backend-py/.venv/bin/pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && /app/backend-py/.venv/bin/pip install --no-cache-dir -r backend-py/requirements.txt

# Build frontend with production mode
# Set npm mirror and build
RUN npm config set registry https://registry.npmmirror.com \
    && cd frontend && npm install && NODE_ENV=production npm run build

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create necessary directories
RUN mkdir -p /app/data /app/downloads /app/temp \
    && mkdir -p /var/log/nginx /var/log/samba \
    && touch /var/log/nginx/access.log /var/log/nginx/error.log

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
ENV PATH="/app/backend-py/.venv/bin:$PATH"

# Expose ports (Web UI, API, SMB)
EXPOSE 80 8080 445 139

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Start script that runs all services
COPY start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

CMD ["/usr/local/bin/start.sh"]
