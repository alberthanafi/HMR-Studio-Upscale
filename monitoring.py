"""System-wide readings; missing sensors are reported as unavailable."""
import os
import subprocess
import threading

import psutil
from PySide6.QtCore import QThread, Signal


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}h {minutes:02d}m {seconds:02d}s' if hours else f'{minutes:02d}m {seconds:02d}s'


def gpu_reading():
    result = subprocess.run(
        ['nvidia-smi', '--id=0', '--query-gpu=utilization.gpu,memory.used,memory.total',
         '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=2,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, check=True)
    values = [part.strip() for part in result.stdout.strip().split(',')]
    if len(values) != 3:
        raise ValueError('Unexpected GPU sensor response')
    def number(value):
        try:
            return float(value)
        except ValueError:
            return None
    return tuple(number(value) for value in values)


class ResourceMonitor(QThread):
    reading = Signal(dict)

    def __init__(self):
        super().__init__()
        self.stop = threading.Event()

    def run(self):
        psutil.cpu_percent()  # Prime the delta measurement.
        while not self.stop.wait(1):
            data = {}
            try:
                ram = psutil.virtual_memory()
                data.update(cpu=psutil.cpu_percent(), ram=ram.percent,
                            ram_used=ram.used / 1024**3, ram_total=ram.total / 1024**3)
            except Exception:
                pass
            try:
                data['gpu'], data['vram_used'], data['vram_total'] = gpu_reading()
            except (OSError, ValueError, subprocess.SubprocessError):
                data.update(gpu=None, vram_used=None, vram_total=None)
            self.reading.emit(data)
