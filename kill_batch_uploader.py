import psutil
import sys
import os

def kill_batch_uploader():
    killed = False
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
                
            cmdline = proc.info['cmdline']
            if cmdline and any('batch_uploader.py' in str(arg) for arg in cmdline):
                print(f"Killing process {proc.info['pid']}: {' '.join(cmdline)}")
                proc.kill()
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if killed:
        print("Batch uploader process(es) killed successfully")
    else:
        print("No batch_uploader.py process found")

if __name__ == '__main__':
    kill_batch_uploader()