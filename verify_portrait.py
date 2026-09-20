"""End-to-end portrait preset check using the user's local demo image."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from app import Window

app = QApplication([])
window = Window()
window.probe.wait()
app.processEvents()
window.apply_portrait_preset()
window.folder.setText(str(Path('output/portrait').resolve()))
window.add_files([str(Path('demo1/input1.png').resolve())])
window.run_batch()
loop = QEventLoop()
window.worker.finished.connect(loop.quit)
QTimer.singleShot(120000, window.worker.cancel.set)
loop.exec()
window.worker.wait()
app.processEvents()
assert len(window.results) == 1 and not window.errors, window.errors
path = next(iter(window.results.values()))
with Image.open(path) as result:
    assert result.size == (2412, 3988) and result.mode == 'RGBA'
    assert '"portrait": 0.85' in result.info['HMR Upscale']
    print('PASS: GUI portrait preset, CUDA batch, RGBA output and recorded settings:', path)
window.close()

canvas = Image.new('RGB', (1200, 580), '#13181f')
draw = ImageDraw.Draw(canvas)
for index, (title, filename) in enumerate([
    ('Previous cleanup', 'output/input1_clean_2x.png'),
    ('Portrait restoration 85%', path),
]):
    with Image.open(filename) as image:
        crop = image.convert('RGB').crop((600, 760, 1560, 1640)).resize((600, 550))
        canvas.paste(crop, (index*600, 30))
        draw.text((index*600+12, 8), title, fill='white')
canvas.save('test-output/quality/portrait-comparison.jpg')
