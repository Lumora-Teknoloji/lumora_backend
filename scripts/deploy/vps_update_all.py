import paramiko
import sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('ssh.lumoraboutique.com', username='bedir', password='2001Bedir..')

cmd = """
cd /var/www/lumora
for dir in */; do
  if [ -d "$dir/.git" ]; then
    echo "Pulling $dir"
    cd "$dir"
    git config --global --add safe.directory /var/www/lumora/$dir || true
    echo '2001Bedir..' | sudo -S git config --global --add safe.directory '*' || true
    echo '2001Bedir..' | sudo -S git fetch --all
    echo '2001Bedir..' | sudo -S git checkout master || echo '2001Bedir..' | sudo -S git checkout main
    echo '2001Bedir..' | sudo -S git reset --hard origin/$(git branch --show-current)
    echo '2001Bedir..' | sudo -S git pull
    cd ..
  fi
done

echo "🔨 Building backend and intelligence on VPS..."
echo '2001Bedir..' | sudo -S docker build -t lumora-backend:latest -f ./lumora-backend/docker/Dockerfile ./lumora-backend
echo '2001Bedir..' | sudo -S docker build -t lumora-intelligence:latest ./lumora-intelligence

cat << 'SHELL_EOF' > /tmp/import_image.sh
#!/bin/bash
docker save lumora-backend:latest | k3s ctr images import -
docker save lumora-intelligence:latest | k3s ctr images import -
kubectl apply -f /var/www/lumora/lumora-backend/k8s/
kubectl rollout restart deploy/lumora-backend -n lumora
kubectl rollout restart deploy/intelligence -n lumora
SHELL_EOF
chmod +x /tmp/import_image.sh
echo '2001Bedir..' | sudo -S /tmp/import_image.sh
"""

stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)

for line in iter(stdout.readline, ""):
    print(line, end="")

exit_status = stdout.channel.recv_exit_status()
client.close()
sys.exit(exit_status)
