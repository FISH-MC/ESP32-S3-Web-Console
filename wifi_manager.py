# wifi_manager.py - WiFi连接管理
import network
import time
import ujson
import gc

def connect_wifi(ssid, password):
    """连接WiFi网络"""
    try:
        print(f"正在连接WiFi: {ssid}")
        
        # 激活STA模式
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        
        # 断开现有连接
        if sta_if.isconnected():
            sta_if.disconnect()
            time.sleep(1)
        
        # 连接新网络
        sta_if.connect(ssid, password)
        
        # 等待连接
        for i in range(30):  # 30秒超时
            if sta_if.isconnected():
                print(f"WiFi连接成功!")
                print(f"IP地址: {sta_if.ifconfig()[0]}")
                
                # 保存配置
                save_wifi_config(ssid, password)
                
                return True
            time.sleep(1)
        
        print("WiFi连接超时")
        return False
        
    except Exception as e:
        print(f"WiFi连接错误: {e}")
        return False

def disconnect_wifi():
    """断开WiFi连接"""
    try:
        sta_if = network.WLAN(network.STA_IF)
        if sta_if.isconnected():
            sta_if.disconnect()
        sta_if.active(False)
        print("WiFi已断开")
        return True
    except:
        return True

def scan_wifi():
    """扫描WiFi网络"""
    try:
        print("正在扫描WiFi...")
        
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        networks = sta_if.scan()
        sta_if.active(False)
        
        result = []
        for net in networks:
            try:
                ssid = net[0].decode('utf-8', 'ignore')
                if ssid and len(ssid) > 0:
                    rssi = net[3]
                    channel = net[2]
                    
                    # 获取安全类型
                    authmode = net[4]
                    security = get_security_type(authmode)
                    
                    result.append({
                        "ssid": ssid,
                        "rssi": rssi,
                        "channel": channel,
                        "security": security
                    })
            except:
                continue
        
        print(f"发现 {len(result)} 个网络")
        return result
        
    except Exception as e:
        print(f"WiFi扫描错误: {e}")
        return []

def get_security_type(authmode):
    """获取安全类型"""
    authmodes = {
        0: "开放",
        1: "WEP",
        2: "WPA-PSK",
        3: "WPA2-PSK",
        4: "WPA/WPA2-PSK"
    }
    return authmodes.get(authmode, "未知")

def save_wifi_config(ssid, password):
    """保存WiFi配置"""
    try:
        config = {"ssid": ssid, "password": password}
        with open("wifi_config.json", "w") as f:
            ujson.dump(config, f)
        print(f"WiFi配置已保存: {ssid}")
        return True
    except:
        return False

def load_wifi_config():
    """加载WiFi配置"""
    try:
        with open("wifi_config.json", "r") as f:
            config = ujson.load(f)
        return config
    except:
        return None

def auto_connect():
    """自动连接保存的WiFi"""
    try:
        config = load_wifi_config()
        if config:
            return connect_wifi(config.get("ssid", ""), config.get("password", ""))
        return False
    except:
        return False

# 测试代码
if __name__ == "__main__":
    # 测试WiFi扫描
    networks = scan_wifi()
    for net in networks:
        print(f"{net['ssid']} - 信号:{net['rssi']}dBm")