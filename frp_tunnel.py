# frp_tunnel.py - ESP32-S3简化FRP隧道
FRP_SERVER_DEFAULT = "1.2.3.4"     # 默认服务器IP（可编辑）
FRP_PORT_DEFAULT   = 80          # 默认端口
FRP_TOKEN_DEFAULT  = ""            # 默认token

import socket
import _thread
import time
import json
import network
import machine

class FRPTunnel:
    def __init__(self):
        self.running = False
        self.client_socket = None
        self.thread_id = None
        self.config = {
            'server': FRP_SERVER_DEFAULT,
            'port': FRP_PORT_DEFAULT,
            'token': FRP_TOKEN_DEFAULT,
            'local_port': 80,
            'remote_port': 8080
        }
        self.load_config()
        
    def load_config(self):
        try:
            with open('frp_config.json', 'r') as f:
                saved_config = json.loads(f.read())
                for key in saved_config:
                    if key in self.config:
                        self.config[key] = saved_config[key]
                print("FRP配置已加载")
        except:
            print("使用默认FRP配置")
            
    def save_config(self):
        try:
            with open('frp_config.json', 'w') as f:
                f.write(json.dumps(self.config))
            print("FRP配置已保存")
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def connect_to_server(self):
        try:
            print(f"连接到FRP服务器 {self.config['server']}:{self.config['port']}")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(10)
            self.client_socket.connect((self.config['server'], self.config['port']))
            print("已连接到FRP服务器")
            auth_data = {
                'type': 'auth',
                'device_id': str(machine.unique_id()),
                'token': self.config['token'],
                'local_port': self.config['local_port'],
                'remote_port': self.config['remote_port']
            }
            auth_json = json.dumps(auth_data)
            self.client_socket.send(auth_json.encode() + b'\n')
            response = self.client_socket.recv(1024)
            print(f"服务器响应: {response.decode()}")
            return True
        except Exception as e:
            print(f"连接FRP服务器失败: {e}")
            self.stop()
            return False
    
    def tunnel_thread(self):
        print("FRP隧道线程启动")
        if not self.connect_to_server():
            return
        local_socket = None
        try:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            local_socket.bind(('0.0.0.0', self.config['local_port']))
            local_socket.listen(1)
            local_socket.settimeout(1)
            print(f"本地监听端口: {self.config['local_port']}")
            while self.running:
                try:
                    local_conn, local_addr = local_socket.accept()
                    print(f"本地连接: {local_addr}")
                    conn_msg = {
                        'type': 'new_connection',
                        'client_id': str(local_addr)
                    }
                    self.client_socket.send(json.dumps(conn_msg).encode() + b'\n')
                    local_conn.settimeout(5)
                    self.client_socket.settimeout(5)
                    try:
                        while True:
                            data = local_conn.recv(1024)
                            if not data: break
                            self.client_socket.send(data)
                        while True:
                            data = self.client_socket.recv(1024)
                            if not data: break
                            local_conn.send(data)
                    except Exception as e:
                        print(f"数据转发错误: {e}")
                    try:
                        local_conn.close()
                    except: pass
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"接受连接错误: {e}")
                    time.sleep(1)
        except Exception as e:
            print(f"隧道错误: {e}")
        finally:
            if local_socket:
                try: local_socket.close()
                except: pass
            if self.client_socket:
                try: self.client_socket.close()
                except: pass
            print("FRP隧道线程结束")
    
    def start(self, server, port, token):
        if self.running: return True
        self.config['server'] = server
        self.config['port'] = port
        self.config['token'] = token
        self.save_config()
        self.running = True
        self.thread_id = _thread.start_new_thread(self.tunnel_thread, ())
        return True
    
    def stop(self):
        self.running = False
        if self.client_socket:
            try: self.client_socket.close()
            except: pass
            self.client_socket = None
        time.sleep(1)
        print("FRP隧道已停止")
        return True
    
    def get_status(self):
        status = {
            'running': self.running,
            'config': self.config,
            'connected': self.client_socket is not None
        }
        return status

tunnel = FRPTunnel()

def start_frp(server=None, port=None, token=None):
    print(f"启动FRP隧道: {server or tunnel.config['server']}:{port or tunnel.config['port']}")
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("错误: 请先连接WiFi")
        return False
    s = server or tunnel.config['server']
    p = port   or tunnel.config['port']
    t = token  if token is not None else tunnel.config['token']
    return tunnel.start(s, p, t)

def stop_frp():
    print("停止FRP隧道")
    return tunnel.stop()

def get_frp_status():
    return tunnel.get_status()