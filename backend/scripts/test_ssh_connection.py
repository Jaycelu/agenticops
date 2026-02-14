"""测试SSH连接"""
import paramiko
import socket
import time

def test_ssh_connection():
    ip = "10.128.254.1"
    username = "admin"
    password = "Tianhe@123"
    port = 22
    
    print(f"正在测试连接到 {ip}:{port}...")
    
    # 先测试TCP连接
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            print(f"✓ TCP端口 {port} 开放")
        else:
            print(f"✗ TCP端口 {port} 不可达")
            return False
    except Exception as e:
        print(f"✗ TCP连接测试失败: {e}")
        return False
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"正在建立SSH连接到 {ip}:{port}...")
        ssh.connect(ip, port=port, username=username, password=password, timeout=30, banner_timeout=30)
        print("✓ SSH连接成功！")
        
        # 使用invoke_shell执行命令
        print("正在执行简单命令 'display version'...")
        shell = ssh.invoke_shell()
        time.sleep(1)  # 等待shell准备好
        
        # 发送命令
        shell.send("display version\n")
        time.sleep(3)  # 等待命令执行
        
        # 读取输出
        output = ""
        while shell.recv_ready():
            output += shell.recv(4096).decode('utf-8', errors='ignore')
        
        print(f"✓ 命令输出长度: {len(output)} 字符")
        print(f"命令输出预览（前500字符）:")
        print(output[:500])
        
        ssh.close()
        return True
        
    except paramiko.AuthenticationException:
        print("✗ 认证失败：用户名或密码错误")
        return False
    except paramiko.SSHException as e:
        print(f"✗ SSH连接失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_ssh_connection()