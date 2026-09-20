import unittest
from types import SimpleNamespace
from unittest.mock import patch
from monitoring import gpu_reading, duration

class MonitoringTests(unittest.TestCase):
    def test_gpu_numbers(self):
        with patch('monitoring.subprocess.run', return_value=SimpleNamespace(stdout='75, 2048, 16384\n')):
            self.assertEqual(gpu_reading(), (75, 2048, 16384))

    def test_missing_gpu_utilization_is_not_zero(self):
        with patch('monitoring.subprocess.run', return_value=SimpleNamespace(stdout='[N/A], 2048, 16384')):
            self.assertEqual(gpu_reading(), (None, 2048, 16384))

    def test_invalid_sensor_response(self):
        with patch('monitoring.subprocess.run', return_value=SimpleNamespace(stdout='')):
            with self.assertRaises(ValueError):
                gpu_reading()

    def test_duration(self):
        self.assertEqual(duration(3661), '1h 01m 01s')
        self.assertEqual(duration(-1), '00m 00s')
