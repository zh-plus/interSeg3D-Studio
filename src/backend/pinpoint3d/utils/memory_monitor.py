import torch
import psutil
import time

def get_gpu_memory_info():
    """获取GPU内存使用信息"""
    if torch.cuda.is_available():
        gpu_memory_allocated = torch.cuda.memory_allocated() / (1024**3)  # GB
        gpu_memory_reserved = torch.cuda.memory_reserved() / (1024**3)    # GB
        gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
        
        return {
            'allocated': gpu_memory_allocated,
            'reserved': gpu_memory_reserved,
            'total': gpu_memory_total,
            'free': gpu_memory_total - gpu_memory_reserved
        }
    return None

def get_system_memory_info():
    """获取系统内存使用信息"""
    memory = psutil.virtual_memory()
    return {
        'total': memory.total / (1024**3),      # GB
        'available': memory.available / (1024**3),  # GB
        'used': memory.used / (1024**3),       # GB
        'percent': memory.percent
    }

def print_memory_status(prefix=""):
    """打印当前内存状态"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    
    print(f"{prefix}[{timestamp}] Memory Status:")
    
    # GPU内存
    gpu_info = get_gpu_memory_info()
    if gpu_info:
        print(f"  GPU: {gpu_info['allocated']:.2f}GB allocated, "
              f"{gpu_info['reserved']:.2f}GB reserved, "
              f"{gpu_info['free']:.2f}GB free")
    
    # 系统内存
    sys_info = get_system_memory_info()
    print(f"  RAM: {sys_info['used']:.2f}GB used, "
          f"{sys_info['available']:.2f}GB available, "
          f"{sys_info['percent']:.1f}% used")

def estimate_cdist_memory(num_points_1, num_points_2, dtype_size=4):
    """估算torch.cdist的内存需求"""
    memory_bytes = num_points_1 * num_points_2 * dtype_size
    memory_gb = memory_bytes / (1024**3)
    return memory_gb

total_memory_20_used = 0
monitor_time = 0

def check_memory_safety(num_points_1, num_points_2, safety_threshold_gb=8.0):
    """检查内存是否安全"""
    global total_memory_20_used, monitor_time
    
    estimated_memory = estimate_cdist_memory(num_points_1, num_points_2)
    
    if estimated_memory > safety_threshold_gb:
        print(f"[WARNING] Estimated cdist memory: {estimated_memory:.2f}GB > {safety_threshold_gb}GB")
        print(f"[WARNING] This may cause CUDA OOM error!")
        return False
    else:
        total_memory_20_used += estimated_memory
        monitor_time += 1
        if monitor_time % 20 == 0:
            # print(f"[INFO] 20_used Total memory used: {total_memory_20_used:.2f}GB")
            monitor_time = 0
            total_memory_20_used = 0
        # print(f"[INFO] Estimated cdist memory: {estimated_memory:.2f}GB (safe)")
        return True

if __name__ == "__main__":
    # 测试内存监控
    print_memory_status()
    
    # 测试内存估算
    test_points_1, test_points_2 = 10000, 15000
    check_memory_safety(test_points_1, test_points_2)
