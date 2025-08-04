import unittest
import numpy as np
import sys
import os

# 添加项目路径
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.core.worker_processes import run_inference, run_postprocess, log_exception

class DummyModel:
    def infer(self, frame):
        return ("raw", [1, 2, 3])

class DummyPostprocessor:
    def process(self, result):
        return {"data": {"bbox": {"rectangles": [], "polygons": {}}}}

class TestWorkerProcesses(unittest.TestCase):
    def test_run_inference_and_postprocess(self):
        model = DummyModel()
        post = DummyPostprocessor()
        frame = np.zeros((5, 5, 3), dtype=np.uint8)
        raw, std = run_inference(model, frame)
        self.assertEqual(raw, "raw")
        self.assertEqual(std, [1, 2, 3])
        result = run_postprocess(post, raw)
        self.assertIn("data", result)

    def test_log_exception_structured(self):
        class DummyExc(Exception):
            pass
        import logging
        import io
        import sys
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        try:
            raise DummyExc("test error")
        except Exception as e:
            log_exception("test_proc", "task1", e, extra={"foo": 123})
        handler.flush()
        log_contents = log_stream.getvalue()
        logger.removeHandler(handler)
        self.assertIn("test_proc", log_contents)
        self.assertIn("foo", log_contents)

    def test_exponential_backoff(self):
        retry_delay = 1
        delays = []
        for _ in range(6):
            delays.append(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
        self.assertEqual(delays, [1, 2, 4, 8, 16, 30])

if __name__ == "__main__":
    unittest.main() 