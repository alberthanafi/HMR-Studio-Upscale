import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from PIL import Image, ImageDraw
from restoration import DamageRepair, Colorizer, enhance_detail


class RestorationTests(unittest.TestCase):
    def test_detail_preserves_faces_and_alpha(self):
        pixels = np.random.default_rng(4).integers(40, 210, (80, 100, 4), dtype=np.uint8)
        image = Image.fromarray(pixels)
        mask = Image.new('L', image.size)
        ImageDraw.Draw(mask).rectangle((20, 20, 60, 60), fill=255)
        result = np.array(enhance_detail(image, mask, hyper=True))
        np.testing.assert_array_equal(result[20:61, 20:61], pixels[20:61, 20:61])
        np.testing.assert_array_equal(result[:, :, 3], pixels[:, :, 3])
        self.assertFalse(np.array_equal(result[:10, :, :3], pixels[:10, :, :3]))

    def test_repair_only_changes_masked_pixels(self):
        repair = DamageRepair.__new__(DamageRepair)
        repair.device = 'cpu'
        repair.model = lambda image, mask: torch.ones_like(image)*.8
        image = Image.new('RGBA', (35, 29), (30, 50, 70, 100))
        mask = Image.new('L', image.size)
        ImageDraw.Draw(mask).rectangle((10, 10, 15, 15), fill=255)
        result = np.array(repair.apply(image, mask))
        before = np.array(image)
        np.testing.assert_array_equal(result[np.array(mask)==0], before[np.array(mask)==0])
        self.assertEqual(result[12, 12, 3], 255)
        self.assertGreater(result[12, 12, 0], 150)

    def test_repair_rejects_invalid_masks(self):
        repair = DamageRepair.__new__(DamageRepair)
        image = Image.new('RGB', (20, 20))
        for mask in [Image.new('L', (10, 10)), Image.new('L', (20, 20)), Image.new('L', (20, 20), 255)]:
            with self.assertRaises(ValueError):
                repair.apply(image, mask)

    def test_colorization_preserves_alpha_and_dimensions(self):
        color = Colorizer.__new__(Colorizer)
        color.device = 'cpu'
        color.model = lambda image: torch.ones((1, 2, 256, 256))*15
        image = Image.new('RGBA', (31, 27), (130, 130, 130, 90))
        result = color.apply(image)
        self.assertEqual(result.size, image.size)
        self.assertEqual(result.getpixel((5, 5))[3], 90)
        self.assertGreater(len(set(result.getpixel((5, 5))[:3])), 1)

    def test_disabled_features_do_not_load_models(self):
        from app import Worker
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.png'
            Image.new('RGB', (31, 29), (60, 100, 130)).save(source)
            options = dict(upscale_enabled=False, device='cpu', scale=1, folder=directory, format='png', portrait=0)
            with patch('app.load_model', side_effect=AssertionError('Should not load model')):
                Worker([source], options).run()
            with Image.open(Path(directory)/'source_1x.png') as result, Image.open(source) as original:
                np.testing.assert_array_equal(np.array(result), np.array(original))


class ToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_portrait_disable_restores_previous_settings(self):
        from app import Window
        window = Window()
        try:
            previous = window.portrait_settings()
            window.portrait_preset.setChecked(True)
            self.assertTrue(window.face_enhancer.isChecked())
            self.assertTrue(window.cleanup.isChecked())
            window.portrait_preset.setChecked(False)
            self.assertEqual(window.portrait_settings(), previous)
            window.colorize.setChecked(True)
            window.upscale_enabled.setChecked(False)
            self.assertFalse(window.model.isEnabled())
            self.assertTrue(window.colorize.isChecked())
        finally:
            window.probe.wait()
            window.close()

    def test_mask_single_click_and_undo(self):
        from mask_editor import MaskEditor
        from PySide6.QtGui import QImage
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        image = QImage(160, 120, QImage.Format_RGB32)
        image.fill(Qt.gray)
        editor = MaskEditor(image)
        editor.show()
        self.app.processEvents()
        try:
            point = editor.canvas.image_rect().center().toPoint()
            QTest.mouseClick(editor.canvas, Qt.LeftButton, pos=point)
            self.assertEqual(editor.canvas.mask.pixelColor(80, 60).red(), 255)
            editor.canvas.undo()
            self.assertEqual(editor.canvas.mask.pixelColor(80, 60).red(), 0)
        finally:
            editor.close()
