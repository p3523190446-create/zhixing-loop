"""Boundaries of the snapshot/job protocol; no real camera/model/control IO."""
import base64
import datetime
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from PIL import Image
from server import Jobs, valid_origin, validate_image, local_source


def body():
    image = io.BytesIO()
    Image.new('RGB', (32, 24), 'red').save(image, format='JPEG')
    return {'image_base64': base64.b64encode(image.getvalue()).decode(), 'question': '有什么？',
            'input_source': 'camera_snapshot', 'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'frame_seq': '42'}


class SnapshotTests(unittest.TestCase):
    def test_local_origins(self):
        for value in ('http://127.0.0.1:8780', 'http://192.168.1.2:8780', 'http://localhost:8797'):
            self.assertTrue(valid_origin(value))
        for value in ('null', 'https://example.org', 'http://192.168.1.2.evil.org', 'http://0.0.0.0', 'http://127.0.0.1/path'):
            self.assertFalse(valid_origin(value))
        with self.assertRaises(ValueError):
            local_source('http://example.org')

    def test_bad_images(self):
        for value in ('garbage', base64.b64encode(b'not a picture').decode(), None, 'x'*3_000_001):
            with self.assertRaises(ValueError):
                validate_image(value)

    def test_stale_and_unlabelled_input(self):
        with tempfile.TemporaryDirectory() as folder:
            jobs = Jobs(Path(folder))
            for change in ({'captured_at': '2000-01-01T00:00:00Z'}, {'input_source': 'live_verified'}, {'question': ''}):
                with self.assertRaises(ValueError):
                    jobs.submit({**body(), **change})

    def test_job_isolated_and_busy(self):
        entered, release = threading.Event(), threading.Event()
        def recognize(raw, question):
            entered.set()
            release.wait(2)
            return {'answer': '测试夹具回答', 'model': 'test_fixture', 'elapsed_ms': 1}
        with tempfile.TemporaryDirectory() as folder, patch('model.recognize', recognize):
            jobs = Jobs(Path(folder))
            first = jobs.submit(body())
            entered.wait(1)
            self.assertEqual(jobs.get(first['id'])['state'], 'running')
            with self.assertRaises(RuntimeError):
                jobs.submit(body())
            release.set()
            until = time.monotonic()+2
            while jobs.active and time.monotonic()<until:
                time.sleep(.01)
            result = jobs.get(first['id'])
            self.assertEqual(result['state'], 'done')
            self.assertEqual(result['frame_seq'], '42')
            self.assertFalse(result['actuation_enabled'])
            self.assertTrue((Path(folder)/(first['id']+'.image')).is_file())
            result['answer'] = 'mutated'
            self.assertNotEqual(jobs.get(first['id'])['answer'], 'mutated')
            self.assertIsNone(jobs.get('unknown'))

    def test_failure_has_no_old_answer(self):
        with tempfile.TemporaryDirectory() as folder, patch('model.recognize', side_effect=TimeoutError('test timeout')):
            jobs = Jobs(Path(folder))
            task = jobs.submit(body())
            until = time.monotonic()+2
            while jobs.active and time.monotonic()<until:
                time.sleep(.01)
            result = jobs.get(task['id'])
            self.assertEqual(result['state'], 'failed')
            self.assertNotIn('answer', result)
            self.assertIn('timeout', result['error'])


if __name__ == '__main__':
    unittest.main()
