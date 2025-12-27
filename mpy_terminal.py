# mpy_terminal.py - MicroPython代码执行器
import gc
import uos
import io
import sys
import micropython
import machine
import time

def execute_code(code, timeout=10):
    """执行MicroPython代码"""
    try:
        # 安全检查
        if len(code) > 4096:  # 限制代码大小
            return "错误: 代码过长（最大4096字符）"
        
        # 禁止的危险操作
        dangerous_keywords = [
            "import os",
            "import sys",
            "__import__",
            "eval(",
            "exec(",
            "compile(",
            "open(",
            "rm ",
            "del ",
            "format("
        ]
        
        for keyword in dangerous_keywords:
            if keyword in code:
                return f"错误: 禁止的操作 '{keyword}'"
        
        # 创建安全执行环境
        safe_globals = {
            'print': safe_print,
            'gc': gc,
            'uos': uos,
            'time': time,
            'machine': machine,
            '__name__': '__main__',
            '__builtins__': {
                'print': safe_print,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'range': range
            }
        }
        
        # 捕获输出
        old_stdout = sys.stdout
        output_buffer = io.StringIO()
        sys.stdout = output_buffer
        
        # 允许中断
        micropython.kbd_intr(3)
        
        try:
            # 编译并执行
            compiled = compile(code, '<user_code>', 'exec')
            exec(compiled, safe_globals)
            result = output_buffer.getvalue()
            
        except SyntaxError as e:
            result = f"语法错误: {e}\n在行: {e.lineno}"
        except Exception as e:
            result = f"运行时错误: {e}"
        finally:
            # 恢复stdout
            sys.stdout = old_stdout
            micropython.kbd_intr(-1)
        
        # 垃圾回收
        gc.collect()
        
        return result.strip() or "执行完成（无输出）"
        
    except MemoryError:
        gc.collect()
        return "错误: 内存不足，请简化代码"
    except Exception as e:
        return f"执行错误: {e}"

def safe_print(*args, **kwargs):
    """安全的print函数"""
    try:
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        output = sep.join(str(arg) for arg in args) + end
        sys.stdout.write(output)
    except:
        sys.stdout.write("[打印错误]\n")

def save_code(code):
    """保存代码到文件"""
    try:
        # 限制代码大小
        if len(code) > 8192:
            return False, "代码太大（最大8KB）"
        
        with open("UserCode.py", "w") as f:
            f.write(code)
        
        gc.collect()
        return True, "代码已保存到 UserCode.py"
    except Exception as e:
        return False, f"保存失败: {e}"

def load_code():
    """从文件加载代码"""
    try:
        with open("UserCode.py", "r") as f:
            code = f.read()
        return True, code
    except OSError:
        # 文件不存在，创建默认文件
        default_code = '''# UserCode.py
# 在这里编写你的MicroPython代码
# 通过Web界面保存的代码将存储在这里

print("欢迎使用ESP32-S3 MPY终端!")
print("设备ID:", machine.unique_id())
print("CPU频率:", machine.freq(), "Hz")
print("可用内存:", gc.mem_free(), "bytes")

# 示例代码
for i in range(3):
    print(f"计数: {i}")
    time.sleep(0.5)

print("代码执行完成!")'''
        
        # 尝试保存默认文件
        try:
            with open("UserCode.py", "w") as f:
                f.write(default_code)
        except:
            pass
        
        return False, default_code
    except Exception as e:
        return False, f"加载失败: {e}"

def get_system_info():
    """获取系统信息"""
    try:
        fs_stats = uos.statvfs('/')
        block_size = fs_stats[0]
        total_blocks = fs_stats[2]
        free_blocks = fs_stats[3]
        
        total_kb = (block_size * total_blocks) // 1024
        free_kb = (block_size * free_blocks) // 1024
        
        info = {
            "cpu_freq": machine.freq() // 1000000,
            "free_mem": gc.mem_free() // 1024,
            "storage": f"{free_kb}/{total_kb} KB",
            "device_id": str(machine.unique_id()[-6:]).upper()
        }
        
        return info
    except:
        return {
            "cpu_freq": 240,
            "free_mem": gc.mem_free() // 1024,
            "storage": "未知",
            "device_id": "ESP32-S3"
        }

# 测试代码
if __name__ == "__main__":
    # 测试代码执行
    test_code = '''
print("测试代码执行...")
print("1 + 2 =", 1 + 2)
print("内存:", gc.mem_free())
print("CPU频率:", machine.freq())
'''
    
    result = execute_code(test_code)
    print("执行结果:")
    print(result)
    
    # 测试保存和加载
    success, msg = save_code(test_code)
    print(f"保存: {msg}")
    
    success, code = load_code()
    print(f"加载: {'成功' if success else '失败'}")
    print(f"代码长度: {len(code)}")