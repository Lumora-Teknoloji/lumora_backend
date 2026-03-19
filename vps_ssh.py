import paramiko
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def run_ssh_command(host, port, username, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {username}@{host}:{port}...")
        client.connect(host, port=port, username=username, password=password, timeout=10)
        print(f"Executing: {command}")
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        print("STDOUT:")
        print(out)
        print("STDERR:")
        print(err)
    except Exception as e:
        print(f"SSH Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    host = "ssh.lumoraboutique.com"
    user = "bedir"
    pwd = "2001Bedir.."
    
    cmd = '''
    cd /var/www/backend/LangChain_backend && \
    git pull origin main && \
    export PATH=$PATH:/usr/local/bin:/opt/homebrew/bin:~/.npm-global/bin && \
    if command -v pm2 > /dev/null; then pm2 restart all; else ~/.npm-global/bin/pm2 restart all || echo "pm2 not found"; fi
    '''
    run_ssh_command(host, 22, user, pwd, cmd)
