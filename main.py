# boot.py - 启动配置
import gc
import machine
import time

print("\n" + "="*50)
print("ESP32-S3 双网站系统启动中...")
print("="*50)

# 清理内存
gc.collect()
print(f"初始内存: {gc.mem_free()} bytes")

# 设置CPU频率
machine.freq(240000000)  # 240 MHz
print(f"CPU频率: {machine.freq() // 1000000} MHz")

# 等待系统稳定
time.sleep(1)

# 导入主程序
try:
    import web_main
    print("主程序导入成功")
    
    # 运行主程序
    web_main.main()
    
except Exception as e:
    print(f"启动错误: {e}")
    print("10秒后重启...")
    time.sleep(10)
    machine.reset()