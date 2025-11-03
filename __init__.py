import psutil
import ctypes
from ctypes import wintypes
import time
import os
import platform
import subprocess
import tempfile
import gc
from server import PromptServer
import comfy.model_management

class AnyType(str):
    """用于表示任意类型的特殊类，在类型比较时总是返回相等"""
    def __eq__(self, _) -> bool:
        return True

    def __ne__(self, __value: object) -> bool:
        return False

any = AnyType("*")

class VRAMCleanup:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "offload_model": ("BOOLEAN", {"default": True}),
                "offload_cache": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "anything": (any, {}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }

    RETURN_TYPES = (any,)
    RETURN_NAMES = ("output",)
    OUTPUT_NODE = True
    FUNCTION = "empty_cache"
    CATEGORY = "Memory Management"
    
    @classmethod
    def IS_CHANGED(s, **kwargs):
        # 返回当前时间戳，确保每次都执行
        return float(time.time())

    def empty_cache(self, offload_model, offload_cache, anything=None, unique_id=None, extra_pnginfo=None):
        try:
            if offload_model:
                comfy.model_management.unload_all_models()
            
            if offload_cache:
                gc.collect()
                comfy.model_management.soft_empty_cache()
                PromptServer.instance.prompt_queue.set_flag("free_memory", True)
            
            print(f"VRAM清理完成 [卸载模型: {offload_model}, 清空缓存: {offload_cache}]")
                
        except Exception as e:
            print(f"VRAM清理失败: {str(e)}")
        
        return (anything,)


class RAMCleanup:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "clean_file_cache": ("BOOLEAN", {"default": True, "label": "清理文件缓存"}),
                "clean_processes": ("BOOLEAN", {"default": True, "label": "清理进程内存"}),
                "clean_dlls": ("BOOLEAN", {"default": True, "label": "清理未使用DLL"}),
                "retry_times": ("INT", {
                    "default": 3, 
                    "min": 1, 
                    "max": 10, 
                    "step": 1,
                    "label": "重试次数"
                }),
            },
            "optional": {
                "anything": (any, {}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }

    RETURN_TYPES = (any,)
    RETURN_NAMES = ("output",)
    OUTPUT_NODE = True
    FUNCTION = "clean_ram"
    CATEGORY = "Memory Management"
    
    @classmethod
    def IS_CHANGED(s, **kwargs):
        # 返回当前时间戳，确保每次都执行
        return float(time.time())

    def get_ram_usage(self):
        memory = psutil.virtual_memory()
        return memory.percent, memory.available / (1024 * 1024) 

    def clean_ram(self, clean_file_cache, clean_processes, clean_dlls, retry_times, anything=None, unique_id=None, extra_pnginfo=None):
        try:
            before_usage, before_available = self.get_ram_usage()
            system = platform.system()
            
            for attempt in range(retry_times):
                if clean_file_cache:
                    try:
                        if system == "Windows":
                            ctypes.windll.kernel32.SetSystemFileCacheSize(-1, -1, 0)
                        elif system == "Linux":
                            subprocess.run(["sudo", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"], 
                                          check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    except:
                        pass
                
                if clean_processes:
                    if system == "Windows":
                        for process in psutil.process_iter(['pid', 'name']):
                            try:
                                handle = ctypes.windll.kernel32.OpenProcess(
                                    wintypes.DWORD(0x001F0FFF),
                                    wintypes.BOOL(False),
                                    wintypes.DWORD(process.info['pid'])
                                )
                                ctypes.windll.psapi.EmptyWorkingSet(handle)
                                ctypes.windll.kernel32.CloseHandle(handle)
                            except:
                                continue

                if clean_dlls:
                    try:
                        if system == "Windows":
                            ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
                        elif system == "Linux":
                            subprocess.run(["sync"], check=True)
                    except:
                        pass

                time.sleep(1)

            after_usage, after_available = self.get_ram_usage()
            freed_mb = after_available - before_available
            print(f"RAM清理完成 [{before_usage:.1f}% → {after_usage:.1f}%, 释放: {freed_mb:.0f}MB]")

        except Exception as e:
            print(f"RAM清理失败: {str(e)}")
            
        return (anything,)
    

NODE_CLASS_MAPPINGS = {
    "VRAMCleanup": VRAMCleanup,
    "RAMCleanup": RAMCleanup,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRAMCleanup": "🎈VRAM-Cleanup",
    "RAMCleanup": "🎈RAM-Cleanup",
}
