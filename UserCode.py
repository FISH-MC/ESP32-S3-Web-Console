# UserCode.py - 用户代码文件
# 这是一个示例文件，用户可以通过Web界面修改和执行这些代码

print("=== UserCode.py 已加载 ===")

def system_info():
    import gc
    import uos
    
    print("\n系统信息:")
    print(f"可用内存: {gc.mem_free()} 字节")
    print(f"已用内存: {gc.mem_alloc()} 字节")
    
    try:
        fs_stats = uos.statvfs('/')
        total = (fs_stats[0] * fs_stats[2]) // 1024
        free = (fs_stats[0] * fs_stats[3]) // 1024
        print(f"存储空间: {free} KB 可用 / {total} KB 总共")
    except:
        print("存储空间: 未知")
"""
def led_blink():
    print("\nLED闪烁测试 (如果GPIO48连接了LED):")
    try:
        from machine import Pin
        led = Pin(48, Pin.OUT)
        for i in range(3):
            led.value(1)
            time.sleep(0.5)
            led.value(0)
            time.sleep(0.5)
        print("LED测试完成")
    except Exception as e:
        print(f"LED测试失败: {e}")
"""

if __name__ == "__main__":
    system_info()
    #def led_blink()
    print("\n=== 执行完成 ===")
