# main.py - ESP32-S3控制台主程序（最终版）
import network
import socket
import time
import machine
import uos
import gc

print("\n" + "="*50)
print("ESP32-S3控制台启动中...")
print("="*50)

# 生成设备ID
def get_device_id():
    uid = machine.unique_id()
    if isinstance(uid, bytes):
        hex_str = ''
        for b in uid[-6:]:
            hex_str = hex_str + '%02X' % b
        device_id = "ESP32-S3-" + hex_str
    else:
        device_id = "ESP32-S3-" + str(uid)[-6:]
    
    return device_id

device_id = get_device_id()
ap_ssid = device_id
ap_password = "12345678"

# ========== 创建AP热点 ==========
ap = network.WLAN(network.AP_IF)
ap.active(False)
time.sleep(0.5)
ap.active(True)
time.sleep(1)

try:
    ap.config(ssid=ap_ssid, password=ap_password, authmode=3, channel=6)
    print("AP配置成功")
except Exception as e:
    print("AP配置失败:", e)
    try:
        ap.config(ssid=ap_ssid)
        print("AP SSID设置成功")
    except:
        print("AP配置完全失败")

try:
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
except Exception as e:
    print("设置IP失败:", e)

time.sleep(2)

print("="*50)
print(f"✓ AP热点已创建")
print(f"  热点名称: {ap_ssid}")
print(f"  热点密码: {ap_password}")
if ap.active():
    ip_info = ap.ifconfig()
    print(f"  IP地址: {ip_info[0]}")
    print(f"  控制台: http://{ip_info[0]}")
else:
    print(f"  AP未激活，请检查配置")
print("="*50)

# 全局状态
global_state = {
    "device_id": device_id,
    "wifi_connected": False,
    "wifi_ssid": "",
    "start_time": time.ticks_ms()
}

# ========== HTTP服务器 ==========
def http_server():
    """HTTP服务器主函数"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 80))
    sock.listen(5)
    
    print("HTTP服务器已启动")
    print("控制台: http://192.168.4.1")
    
    while True:
        conn = None
        try:
            conn, addr = sock.accept()
            conn.settimeout(10.0)  # 设置连接超时时间
            
            try:
                request = conn.recv(1024)
                if not request:
                    conn.close()
                    continue
                
                request_str = request.decode('utf-8', 'ignore')
                lines = request_str.split('\r\n')
                
                if not lines:
                    conn.close()
                    continue
                
                request_line = lines[0]
                parts = request_line.split()
                if len(parts) < 2:
                    conn.close()
                    continue
                
                method = parts[0]
                path = parts[1]
                
                # 简化路径处理
                if path == '/' or 'index' in path:
                    response = get_html_response()
                elif path == '/status':
                    response = get_status_response()
                elif 'wifi/connect' in path:
                    response = handle_wifi_connect(path)
                elif path == '/wifi/disconnect':
                    response = handle_wifi_disconnect()
                elif path == '/wifi/scan':
                    response = handle_wifi_scan()
                elif 'cpu_freq' in path:
                    response = handle_cpu_freq(path)
                elif path == '/restart':
                    response = handle_restart()
                elif 'gpio' in path:
                    response = handle_gpio(path)
                elif path == '/factory_reset':
                    response = handle_factory_reset()
                else:
                    response = get_html_response()
                
                # 发送响应
                try:
                    conn.send(response.encode('utf-8'))
                except Exception as e:
                    # 客户端在发送过程中断开连接，这是正常的
                    if "ECONNRESET" in str(e) or "104" in str(e):
                        pass  # 忽略这个错误
                    else:
                        print("发送响应错误:", e)
                
            except Exception as e:
                # 处理请求时出错
                if "ECONNRESET" in str(e) or "104" in str(e):
                    pass  # 忽略连接重置错误
                else:
                    print("请求处理错误:", e)
            
        except Exception as e:
            # 接受连接时出错
            if "ECONNRESET" in str(e) or "104" in str(e):
                pass  # 忽略连接重置错误
            else:
                print("服务器错误:", e)
            time.sleep(0.1)
            
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            gc.collect()

def get_html_response():
    """返回HTML页面"""
    try:
        f = open('DOCTYPE.html')
        html = f.read()
        f.close()
        
        # 替换占位符
        html = html.replace('{device_id}', device_id)
        
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/html\r\n"
        response += "\r\n"
        response += html
        
        return response
    except Exception as e:
        print("读取HTML文件错误:", e)
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/html\r\n"
        response += "\r\n"
        response += "<html><body><h1>" + device_id + "</h1><p>ESP32-S3控制台</p></body></html>"
        return response

def get_status_response():
    """返回状态JSON"""
    gc.collect()
    
    status = '{'
    status += '"device_id":"' + device_id + '",'
    status += '"cpu_freq":' + str(machine.freq() // 1000000) + ','
    status += '"free_mem":' + str(gc.mem_free() // 1024) + ','
    status += '"wifi_connected":' + ('true' if global_state["wifi_connected"] else 'false') + ','
    status += '"wifi_ssid":"' + global_state["wifi_ssid"] + '",'
    status += '"uptime":' + str((time.ticks_ms() - global_state["start_time"]) // 1000)
    status += '}'
    
    return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + status

def handle_wifi_connect(path):
    """处理WiFi连接"""
    try:
        if '?' in path:
            params = path.split('?')[1]
            parts = params.split('&')
            ssid = None
            password = None
            
            for part in parts:
                if part.startswith('ssid='):
                    ssid = part[5:]
                    ssid = ssid.replace('%20', ' ').replace('+', ' ')
                elif part.startswith('password='):
                    password = part[9:]
                    password = password.replace('%20', ' ').replace('+', ' ')
            
            if ssid and password:
                print("连接WiFi:", ssid)
                
                wlan = network.WLAN(network.STA_IF)
                wlan.active(True)
                wlan.connect(ssid, password)
                
                for i in range(20):
                    if wlan.isconnected():
                        global_state["wifi_connected"] = True
                        global_state["wifi_ssid"] = ssid
                        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nWiFi连接成功: " + ssid
                    time.sleep(0.5)
                
                return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nWiFi连接超时"
        
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n缺少参数"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n错误: " + str(e)

def handle_wifi_disconnect():
    """断开WiFi"""
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            wlan.disconnect()
        wlan.active(False)
        
        global_state["wifi_connected"] = False
        global_state["wifi_ssid"] = ""
        
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nWiFi已断开"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n错误: " + str(e)

def handle_wifi_scan():
    """扫描WiFi"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        networks = wlan.scan()
        wlan.active(False)
        
        result = '['
        first = True
        
        for net in networks:
            try:
                ssid = net[0].decode('utf-8', 'ignore')
                if ssid and len(ssid) > 0:
                    if not first:
                        result += ','
                    result += '{"ssid":"' + ssid + '","rssi":' + str(net[3]) + ',"channel":' + str(net[2]) + '}'
                    first = False
            except:
                continue
        
        result += ']'
        
        return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + result
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n扫描失败: " + str(e)

def handle_cpu_freq(path):
    """设置CPU频率"""
    try:
        if 'value=' in path:
            parts = path.split('value=')
            freq_str = parts[1].split('&')[0]
            freq = int(freq_str)
            
            machine.freq(freq * 1000000)
            
            return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nCPU频率已设置为 " + str(freq) + " MHz"
        else:
            return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n缺少频率参数"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n错误: " + str(e)

def handle_restart():
    """重启系统"""
    response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n设备正在重启..."
    # 延迟发送重启响应
    time.sleep(1)
    machine.reset()
    return response

def handle_gpio(path):
    """处理GPIO控制"""
    try:
        if 'set' in path and '?' in path:
            params = path.split('?')[1]
            parts = params.split('&')
            pin = None
            value = None
            
            for part in parts:
                if part.startswith('pin='):
                    pin = int(part[4:])
                elif part.startswith('value='):
                    value = int(part[6:])
            
            if pin is not None and value is not None:
                p = machine.Pin(pin, machine.Pin.OUT)
                p.value(value)
                return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nGPIO " + str(pin) + " 设置为 " + str(value)
        
        elif 'read' in path and '?' in path:
            params = path.split('?')[1]
            parts = params.split('&')
            for part in parts:
                if part.startswith('pin='):
                    pin = int(part[4:])
                    p = machine.Pin(pin, machine.Pin.IN)
                    value = p.value()
                    return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" + str(value)
        
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n无效的GPIO请求"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nGPIO错误: " + str(e)

def handle_factory_reset():
    """恢复出厂设置"""
    try:
        files = ["wifi_config.json", "config.json", "settings.json"]
        for file in files:
            try:
                uos.remove(file)
            except:
                pass
                
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n恢复出厂设置完成"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n恢复失败: " + str(e)

# ========== 主程序 ==========
def main():
    print("内存使用情况:")
    print("初始内存:", gc.mem_free(), "bytes")
    
    gc.collect()
    print("清理后内存:", gc.mem_free(), "bytes")
    
    print("\n系统启动完成！")
    print("1. 连接WiFi热点:", ap_ssid)
    print("2. 密码:", ap_password)
    print("3. 在浏览器中打开: http://192.168.4.1")
    print("4. 或打开: http://" + ap.ifconfig()[0])
    
    http_server()

if __name__ == "__main__":
    main()