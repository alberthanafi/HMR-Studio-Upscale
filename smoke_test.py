"""Optional end-to-end verification: downloads official models and runs CUDA."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageDraw
from engine import ROOT, MODELS, load_model, upscale, save_output

def main():
    folder = ROOT / 'test-output'
    folder.mkdir(exist_ok=True)
    source = folder / 'sample.png'
    image = Image.new('RGBA', (97, 73), (28, 41, 65, 230))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 10, 62, 65), fill=(100, 230, 185, 255))
    draw.line((0, 70, 96, 0), fill='white', width=2)
    image.save(source)
    print('GPU:', torch.cuda.get_device_name(0), 'Torch:', torch.__version__, flush=True)
    for name in MODELS:
        model = load_model(name, 'cuda', True, print)
        result = upscale(source, model, 4, 64)
        assert result.size == (388, 292) and result.mode == 'RGBA'
        assert np.array(result)[:, :, :3].std() > 0
        path = save_output(result, source, folder, 4)
        print('PASS:', name, path, flush=True)
        del model
        torch.cuda.empty_cache()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from app import Window, STYLE, Worker
    from PySide6.QtCore import QEventLoop, QTimer
    app = QApplication([])
    for font in ['segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf']:
        QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Window()
    window.add_files([str(source)])
    window.completed(str(source.resolve()), str(path))
    window.show()
    app.processEvents()
    window.grab().save(str(folder / 'interface.png'))
    window.probe.wait()
    sensor_loop = QEventLoop()
    window.monitor.reading.connect(sensor_loop.quit)
    QTimer.singleShot(10000, sensor_loop.quit)
    sensor_loop.exec()
    app.processEvents()
    assert 'measuring' not in window.cpu_readout.text()
    assert 'unavailable' not in window.gpu_readout.text()
    window.grab().save(str(folder / 'interface.png'))
    window.close()
    print('PASS: GUI construction, queue and comparison preview', flush=True)
    corrupt = folder / 'corrupt.png'
    corrupt.write_bytes(b'not an image')
    options = dict(model=next(iter(MODELS)), device='cuda', half=True,
                   scale=2, tile=64, folder=str(folder), format='png')
    worker = Worker([corrupt, source], options)
    successes, failures = [], []
    details = []
    worker.detail.connect(details.append)
    worker.completed.connect(lambda a, b: successes.append(b))
    worker.failed.connect(lambda a, b: failures.append(b))
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(worker.cancel.set)
    timer.start(60000)
    worker.start()
    loop.exec()
    worker.wait()
    timer.stop()
    assert len(successes) == 1 and len(failures) == 1, (successes, failures)
    assert any(info.get('eta') is not None for info in details)
    assert any(info['stage'] == 'Saving image' for info in details)
    print('PASS: background batch continues after a corrupt file', flush=True)
    print('PASS: live system sensors, tile progress and ETA', flush=True)

if __name__ == '__main__':
    main()
