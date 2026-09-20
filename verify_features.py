"""Optional real-model smoke test for the complete restoration pipeline."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, Qt, QPoint
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtTest import QTest
from app import Window, STYLE
from mask_editor import MaskEditor

def main():
    app = QApplication([])
    app.setStyleSheet(STYLE)
    for name in ['segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf']:
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)
    folder = Path('test-output/features').resolve()
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'pipeline-damage.png'
    original = Image.open('demo1/input1.png').convert('RGB')
    original.thumbnail((384, 640))
    original = original.convert('L').convert('RGB')
    mask = Image.new('L', original.size)
    draw = ImageDraw.Draw(mask)
    draw.line((10, 45, 140, 500), fill=255, width=5)
    draw.rectangle((250, 450, 280, 490), fill=255)
    original.paste('white', mask=mask)
    original.save(source)
    mask_path = folder / 'pipeline-mask.png'
    mask.save(mask_path)
    window = Window()
    previous_folder = window.settings.value('folder')
    try:
        window.probe.wait()
        app.processEvents()
        window.add_files([str(source)])
        window.portrait_preset.setChecked(True)
        window.colorize.setChecked(True)
        window.detail_enabled.setChecked(True)
        window.hyper.setChecked(True)
        window.repair_enabled.setChecked(True)
        window.damage_masks[str(source)] = str(mask_path)
        window.folder.setText(str(folder))
        window.run_batch()
        loop = QEventLoop()
        window.worker.finished.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(window.worker.cancel.set)
        timer.start(120000)
        loop.exec()
        window.worker.wait()
        timer.stop()
        app.processEvents()
        assert window.results and not window.errors, window.activity.toPlainText()
        result_path = next(iter(window.results.values()))
        with Image.open(result_path) as result:
            assert result.size == (original.width*2, original.height*2)
            assert '"colorize": true' in result.info['HMR Upscale']
        window.show()
        app.processEvents()
        window.grab().save(str(folder/'feature-interface.png'))
        print('PASS: repair + colorize + Real-ESRGAN + protected detail + hyper detail + face_enhancer on CUDA', flush=True)
        print(result_path, flush=True)
        editor = MaskEditor(QImage(str(source)), parent=window)
        editor.show()
        app.processEvents()
        point = editor.canvas.image_rect().center().toPoint()
        QTest.mouseClick(editor.canvas, Qt.LeftButton, pos=point)
        assert editor.canvas.mask.pixelColor(editor.canvas.mask.width()//2, editor.canvas.mask.height()//2).red() == 255
        editor.canvas.undo()
        assert editor.canvas.mask.pixelColor(editor.canvas.mask.width()//2, editor.canvas.mask.height()//2).red() == 0
        QTest.mouseClick(editor.canvas, Qt.LeftButton, pos=point)
        editor.grab().save(str(folder/'mask-editor.png'))
        editor.reject()
        print('PASS: painting and undo in per-image mask editor', flush=True)
    finally:
        if window.worker and window.worker.isRunning():
            window.worker.cancel.set()
            window.worker.wait()
        window.settings.setValue('folder', previous_folder)
        window.probe.wait()
        window.close()

if __name__ == '__main__':
    main()
