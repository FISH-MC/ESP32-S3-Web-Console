import network
import socket
import time
import machine
import uos
import gc
import frp_tunnel

print("\n" + "="*50)
print("ESP32-S3控制台启动中...")
print("="*50)

def get_device_id():
    uid = machine.unique_id()
    if isinstance(uid, bytes):
        hex_str = ''.join('%02X' % b for b in uid[-6:])
        device_id = "ESP32-S3-" + hex_str
    else:
        device_id = "ESP32-S3-" + str(uid)[-6:]
    return device_id

device_id = get_device_id()
ap_ssid = device_id
ap_password = "12345678"
ap = network.WLAN(network.AP_IF)
ap.active(False)
time.sleep(0.5)
ap.active(True)
time.sleep(1)
try:
    ap.config(ssid=ap_ssid, password=ap_password, authmode=3, channel=6)
except: pass
ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
time.sleep(2)
global_state = {
    "device_id": device_id,
    "wifi_connected": False,
    "wifi_ssid": "",
    "start_time": time.ticks_ms(),
    "frp_running": False,
}

def http_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 80))
    sock.listen(5)
    while True:
        conn = None
        try:
            conn, addr = sock.accept()
            conn.settimeout(10.0)
            try:
                request = conn.recv(1024)
                if not request: conn.close(); continue
                request_line = request.decode('utf-8', 'ignore').split('\r\n')[0]
                parts = request_line.split()
                if len(parts)<2: conn.close(); continue
                method, path = parts[0], parts[1]
                # --- 路由分发 ----
                if path == '/' or 'index' in path:
                    response = get_html_response()
                elif path.startswith('/status'): response = get_status_response()
                elif 'wifi/connect' in path: response = handle_wifi_connect(path)
                elif path.startswith('/wifi/disconnect'): response = handle_wifi_disconnect()
                elif path.startswith('/wifi/scan'): response = handle_wifi_scan()
                elif 'cpu_freq' in path: response = handle_cpu_freq(path)
                elif path.startswith('/restart'): response = handle_restart()
                elif '/gpio/set' in path or '/gpio/read' in path: response = handle_gpio(path)
                elif path.startswith('/factory_reset'): response = handle_factory_reset()
                elif '/gpio/wave' in path: response = handle_gpio_wave(path)
                elif path.startswith('/frp/start'): response = start_frp_wrap()
                elif path.startswith('/frp/stop'): response = stop_frp_wrap()
                elif path.startswith('/frp/config'): response = handle_frp_config(path)
                else: response = get_html_response()
                conn.send(response.encode('utf-8'))
            except Exception as e:
                print('请求处理错误:',e)
        except Exception as e:
            print('服务器错误:', e)
        finally:
            if conn:
                try: conn.close()
                except: pass
            gc.collect()

def get_html_response():
    try:
        f = open('DOCTYPE.html')
        html = f.read()
        f.close()
        html = html.replace('{device_id}', device_id)
        return "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n读取HTML失败"

def get_status_response():
    gc.collect()
    status = '{'
    status += '"device_id":"' + device_id + '",'
    status += '"cpu_freq":' + str(machine.freq() // 1000000) + ','
    status += '"free_mem":' + str(gc.mem_free() // 1024) + ','
    status += '"wifi_connected":' + ('true' if global_state["wifi_connected"] else 'false') + ','
    status += '"wifi_ssid":"' + global_state["wifi_ssid"] + '",'
    status += '"uptime":' + str((time.ticks_ms() - global_state["start_time"]) // 1000) + ','
    status += '"frp_running":' + ('true' if global_state.get("frp_running", False) else 'false')
    status += '}'
    return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + status

def handle_wifi_connect(path):
    try:
        if '?' in path:
            params = path.split('?')[1]
            parts = params.split('&')
            ssid, password = None, None
            for part in parts:
                if part.startswith('ssid='):     ssid = part[5:].replace('%20', ' ').replace('+', ' ')
                elif part.startswith('password='):password = part[9:].replace('%20', ' ').replace('+', ' ')
            if ssid and password:
                wlan = network.WLAN(network.STA_IF)
                wlan.active(True); wlan.connect(ssid, password)
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
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected(): wlan.disconnect()
        wlan.active(False)
        global_state["wifi_connected"] = False; global_state["wifi_ssid"] = ""
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nWiFi已断开"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n错误: " + str(e)

def handle_wifi_scan():
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        networks = wlan.scan()
        wlan.active(False)
        result = [ ]
        for net in networks:
            try: ssid = net[0].decode('utf-8', 'ignore')
            except: ssid = str(net[0])
            if not ssid: continue
            result.append({'ssid': ssid, 'rssi': net[3], 'channel': net[2]})
        import ujson
        return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + ujson.dumps(result)
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n扫描失败: " + str(e)

def handle_cpu_freq(path):
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
    import _thread
    def reset_async():
        time.sleep(1)
        machine.reset()
    _thread.start_new_thread(reset_async, ())
    return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n设备正在重启..."

def handle_factory_reset():
    try:
        files = ["wifi_config.json", "config.json", "settings.json", "frp_config.json"]
        for file in files:
            try: uos.remove(file)
            except: pass
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n恢复出厂设置完成"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n恢复失败: " + str(e)

def handle_gpio(path):
    try:
        pin=None; value=None
        if '/gpio/set' in path and '?' in path:
            params = path.split('?')[1]
            for p in params.split('&'):
                if p.startswith('pin='): pin = int(p[4:])
                elif p.startswith('value='): value = int(p[6:])
            if pin is not None and value is not None:
                p = machine.Pin(pin, machine.Pin.OUT)
                p.value(value)
                return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nGPIO " + str(pin) + " 设置为 " + str(value)
        elif '/gpio/read' in path and '?' in path:
            params = path.split('?')[1]
            for p in params.split('&'):
                if p.startswith('pin='):
                    pin = int(p[4:])
                    p = machine.Pin(pin, machine.Pin.IN)
                    val = p.value()
                    return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" + str(val)
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n无效的GPIO请求"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nGPIO错误: " + str(e)

def handle_gpio_wave(path):
    try:
        params = path.split('?')[1] if '?' in path else ""
        args = {}
        for p in params.split('&'):
            if '=' in p:
                k,v=p.split('=',1); args[k]=v
        pin = int(args.get('pin', 14))
        wave_type = args.get('type','square')
        freq = int(args.get('freq', 1))
        duty = int(args.get('duty', 50))  # 0-100
        import math, _thread
        if wave_type == 'square':
            def _square_wave():
                p=machine.Pin(pin, machine.Pin.OUT)
                t = 1/(freq*2)
                for _ in range(2000):
                    p.value(1); time.sleep(t*duty/50)
                    p.value(0); time.sleep(t*(100-duty)/50)
            _thread.start_new_thread(_square_wave, ())
            return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n输出方波已开始"
        elif wave_type == 'sin':
            def _sin_wave():
                p=machine.PWM(machine.Pin(pin))
                p.freq(freq)
                import math
                for t in range(2000):
                    v=int((math.sin(2*math.pi*freq*t/2000)+1)*511)
                    p.duty(v)
                    time.sleep(0.005)
                p.deinit()
            _thread.start_new_thread(_sin_wave, ())
            return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n输出正弦波已开始"
        else:
            return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n不支持的波形"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nGPIO波形错误: " + str(e)

def start_frp_wrap():
    try:
        ok = frp_tunnel.start_frp()
        global_state["frp_running"] = True
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n隧道已启动"
    except Exception as e:
        global_state["frp_running"] = False
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nFRP启动失败: " + str(e)

def stop_frp_wrap():
    try:
        ok = frp_tunnel.stop_frp()
        global_state["frp_running"] = False
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n隧道已停止"
    except Exception as e:
        return "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nFRP停止失败: " + str(e)

def handle_frp_config(path):
    import ujson
    if '?' in path:
        params = path.split('?', 1)[1]
        kv_list = [x.split('=',1) for x in params.split('&') if '=' in x]
        kv = {k: v for k, v in kv_list}
        changed = False
        if 'server' in kv:
            frp_tunnel.tunnel.config['server'] = kv['server']
            changed = True
        if 'port' in kv:
            frp_tunnel.tunnel.config['port'] = int(kv['port'])
            changed = True
        if 'token' in kv:
            frp_tunnel.tunnel.config['token'] = kv['token']
            changed = True
        if changed:
            frp_tunnel.tunnel.save_config()
    config = {
        "server": frp_tunnel.tunnel.config.get("server",""),
        "port": frp_tunnel.tunnel.config.get("port",""),
        "token": frp_tunnel.tunnel.config.get("token","")
    }
    return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + ujson.dumps(config)

def main():
    http_server()

if __name__ == "__main__":
    main()