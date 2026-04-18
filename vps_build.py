import paramiko
import sys
import base64

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
client.connect('ssh.lumoraboutique.com', username='bedir', password='2001Bedir..')

with open('app/routers/scraper.py', 'rb') as f:
    scraper_b64 = base64.b64encode(f.read()).decode('utf-8')

dockerfile = """
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

RUN apt-get update && apt-get install -y gcc postgresql-client wget gnupg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy explicitly!
COPY Scrapper_context /Scrapper
RUN pip install --no-cache-dir -r /Scrapper/requirements.txt || true

COPY . .

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV DEBIAN_FRONTEND=noninteractive

EXPOSE 8000
CMD ["python", "run_server.py"]
"""

cmd = f"""
cd /var/www/lumora/lumora-backend

# Push the modified scraper.py
echo '{scraper_b64}' | base64 -d > app/routers/scraper.py

cat << 'DOCKERFILE' > Dockerfile
{dockerfile}
DOCKERFILE

echo "📦 Preparing Scrapper context on VPS..."
rm -rf Scrapper_context
cp -r ../scrapper Scrapper_context

echo "🔨 Building lumora-backend:latest on VPS..."
echo '2001Bedir..' | sudo -S docker build -t lumora-backend:latest .

echo "🧹 Cleaning up context..."
rm -rf Scrapper_context

echo "📦 Saving and importing image to K3s containerd..."
cat << 'SHELL_EOF' > /tmp/import_image.sh
#!/bin/bash
docker save lumora-backend:latest | k3s ctr images import -
SHELL_EOF
chmod +x /tmp/import_image.sh
echo '2001Bedir..' | sudo -S /tmp/import_image.sh

echo "🔄 Restarting Kubernetes deployment..."
echo '2001Bedir..' | sudo -S kubectl rollout restart deploy/lumora-backend -n lumora
"""

stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)

for line in iter(stdout.readline, ""):
    print(line, end="")

exit_status = stdout.channel.recv_exit_status()
client.close()
sys.exit(exit_status)
