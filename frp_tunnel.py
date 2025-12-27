# frp_tunnel.py - ESP32-S3简化FRP隧道
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
            'server': 'frp.example.com',
            'port': 7000,
            'token': '',
            'local_port': 80,
            'remote_port': 8080
        }
        self.load_config()
        
    def load_config(self):
        """加载配置"""
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
        """保存配置"""
        try:
            with open('frp_config.json', 'w') as f:
                f.write(json.dumps(self.config))
            print("FRP配置已保存")
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def connect_to_server(self):
        """连接到FRP服务器"""
        try:
            print(f"连接到FRP服务器 {self.config['server']}:{self.config['port']}")
            
            # 创建socket
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(10)
            
            # 连接服务器
            self.client_socket.connect((self.config['server'], self.config['port']))
            print("已连接到FRP服务器")
            
            # 发送认证信息（简化版）
            auth_data = {
                'type': 'auth',
                'device_id': machine.unique_id(),
                'token': self.config['token'],
                'local_port': self.config['local_port'],
                'remote_port': self.config['remote_port']
            }
            
            auth_json = json.dumps(auth_data)
            self.client_socket.send(auth_json.encode() + b'\n')
            
            # 接收响应
            response = self.client_socket.recv(1024)
            print(f"服务器响应: {response.decode()}")
            
            return True
            
        except Exception as e:
            print(f"连接FRP服务器失败: {e}")
            self.stop()
            return False
    
    def forward_data(self, local_conn, remote_conn):
        """转发数据"""
        try:
            while self.running:
                try:
                    # 从本地接收数据
                    data = local_conn.recv(1024)
                    if not data:
                        break
                    
                    # 转发到远程
                    remote_conn.send(data)
                    
                except:
                    break
        except:
            pass
    
    def tunnel_thread(self):
        """隧道线程主函数"""
        print("FRP隧道线程启动")
        
        # 连接到FRP服务器
        if not self.connect_to_server():
            return
        
        # 创建本地监听socket
        local_socket = None
        try:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            local_socket.bind(('0.0.0.0', self.config['local_port']))
            local_socket.listen(1)
            local_socket.settimeout(1)
            
            print(f"本地监听端口: {self.config['local_port']}")
            
            # 主循环
            while self.running:
                try:
                    # 等待本地连接
                    local_conn, local_addr = local_socket.accept()
                    print(f"本地连接: {local_addr}")
                    
                    # 通知服务器新连接
                    conn_msg = {
                        'type': 'new_connection',
                        'client_id': str(local_addr)
                    }
                    self.client_socket.send(json.dumps(conn_msg).encode() + b'\n')
                    
                    # 设置超时
                    local_conn.settimeout(5)
                    self.client_socket.settimeout(5)
                    
                    # 简单的数据转发
                    try:
                        # 从客户端接收并转发到服务器
                        while True:
                            try:
                                data = local_conn.recv(1024)
                                if not data:
                                    break
                                self.client_socket.send(data)
                            except:
                                break
                        
                        # 从服务器接收并转发到客户端
                        while True:
                            try:
                                data = self.client_socket.recv(1024)
                                if not data:
                                    break
                                local_conn.send(data)
                            except:
                                break
                                
                    except Exception as e:
                        print(f"数据转发错误: {e}")
                    
                    # 关闭本地连接
                    try:
                        local_conn.close()
                    except:
                        pass
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"接受连接错误: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f"隧道错误: {e}")
        finally:
            # 清理
            if local_socket:
                try:
                    local_socket.close()
                except:
                    pass
                    
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
                
            print("FRP隧道线程结束")
    
    def start(self, server, port, token):
        """启动FRP隧道"""
        if self.running:
            return True
            
        # 更新配置
        self.config['server'] = server
        self.config['port'] = port
        self.config['token'] = token
        self.save_config()
        
        # 启动线程
        self.running = True
        self.thread_id = _thread.start_new_thread(self.tunnel_thread, ())
        
        return True
    
    def stop(self):
        """停止FRP隧道"""
        self.running = False
        
        # 关闭socket
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
            
        # 等待线程结束
        time.sleep(1)
        print("FRP隧道已停止")
        return True
    
    def get_status(self):
        """获取状态"""
        status = {
            'running': self.running,
            'config': self.config,
            'connected': self.client_socket is not None
        }
        return status

# 全局实例
tunnel = FRPTunnel()

# API函数
def start_frp(server="frp.example.com", port=7000, token=""):
    """启动FRP隧道"""
    print(f"启动FRP隧道: {server}:{port}")
    
    # 检查WiFi连接
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("错误: 请先连接WiFi")
        return False
    
    # 启动隧道
    success = tunnel.start(server, port, token)
    
    if success:
        print("FRP隧道启动成功")
        return True
    else:
        print("FRP隧道启动失败")
        return False

def stop_frp():
    """停止FRP隧道"""
    print("停止FRP隧道")
    return tunnel.stop()

def get_frp_status():
    """获取FRP状态"""
    return tunnel.get_status()

# 测试函数
def test_frp():
    """测试FRP功能"""
    print("测试FRP隧道...")
    
    # 模拟配置
    config = {
        'server': 'test.server.com',
        'port': 7000,
        'token': 'test123'
    }
    
    # 测试连接（需要实际的FRP服务器才能测试）
    print("注意: 需要配置实际的FRP服务器才能测试")
    print(f"配置: {config}")
    
    return False

if __name__ == "__main__":
    print("FRP隧道模块加载完成")
    print("可用函数:")
    print("  start_frp(server, port, token) - 启动FRP隧道")
    print("  stop_frp() - 停止FRP隧道")
    print("  get_frp_status() - 获取状态")