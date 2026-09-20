import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from engine import upscale, save_output, Cancelled

class NearestModel:
    scale = 2
    device = 'cpu'
    dtype = torch.float32
    def __call__(self, value):
        return torch.nn.functional.interpolate(value, scale_factor=2, mode='nearest')

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def test_tiling_matches_whole_image_on_odd_dimensions(self):
        pixels = np.random.default_rng(7).integers(0, 256, (73, 97, 3), dtype=np.uint8)
        source = self.root / 'input.png'
        Image.fromarray(pixels).save(source)
        progress = []
        result = upscale(source, NearestModel(), 2, 32, progress.append)
        expected = pixels.repeat(2, axis=0).repeat(2, axis=1)
        np.testing.assert_array_equal(np.array(result), expected)
        self.assertEqual(progress[-1], 1)
        self.assertGreater(len(progress), 1)
    def test_alpha_and_non_native_scale(self):
        source = self.root / 'alpha.png'
        Image.new('RGBA', (19, 13), (100, 120, 140, 80)).save(source)
        result = upscale(source, NearestModel(), 3, 16)
        self.assertEqual(result.size, (57, 39))
        self.assertEqual(result.getpixel((10, 10))[3], 80)
    def test_cancel(self):
        source = self.root / 'input.png'
        Image.new('RGB', (20, 20)).save(source)
        with self.assertRaises(Cancelled):
            upscale(source, NearestModel(), cancel=lambda: True)
    def test_cleanup_preserves_requested_dimensions_and_alpha(self):
        source = self.root / 'odd.png'
        Image.new('RGBA', (19, 13), (120, 80, 60, 75)).save(source)
        result = upscale(source, NearestModel(), 2, 16, cleanup=True)
        self.assertEqual(result.size, (38, 26))
        self.assertEqual(result.getpixel((10, 10))[3], 75)

    def test_png_records_processing_settings(self):
        path = save_output(Image.new('RGB', (10, 10)), 'sample.png', self.root, 2,
                           metadata={'cleanup': True, 'model': 'test'})
        import json
        with Image.open(path) as result:
            self.assertEqual(json.loads(result.info['HMR Upscale'])['cleanup'], True)
    def test_unique_output_and_jpeg_alpha(self):
        image = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        first = save_output(image, 'test.png', self.root, 4, 'jpg')
        second = save_output(image, 'test.png', self.root, 4, 'jpg')
        self.assertNotEqual(first, second)
        with Image.open(first) as result:
            self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
    def test_reject_16_bit(self):
        source = self.root / '16.png'
        Image.new('I;16', (10, 10)).save(source)
        with self.assertRaisesRegex(ValueError, '16-bit'):
            upscale(source, NearestModel())

if __name__ == '__main__':
    unittest.main()
