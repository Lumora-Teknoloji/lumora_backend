import paramiko
import sys
import base64

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('ssh.lumoraboutique.com', username='bedir', password='2001Bedir..')

with open('app/routers/scraper.py', 'rb') as f:
    scraper_b64 = base64.b64encode(f.read()).decode('utf-8')

cmd = f"""
cd /var/www/lumora/lumora-backend
echo '{scraper_b64}' | base64 -d > app/routers/scraper.py

echo "🔨 Building lumora-backend:latest on VPS..."
echo '2001Bedir..' | sudo -S docker build -t lumora-backend:latest -f docker/Dockerfile .

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
