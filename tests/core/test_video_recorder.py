"""
视频录制器单元测试
测试FFmpegVideoRecorder模块的核心功能
"""

import unittest
import tempfile
import os
import sys
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.video_recorder import FFmpegVideoRecorder


class TestFFmpegVideoRecorder(unittest.TestCase):
    """FFmpeg视频录制器测试类"""
    
    def setUp(self):
        """测试前设置"""
        self.video_recorder = FFmpegVideoRecorder()
        
    def test_video_recorder_init(self):
        """测试视频录制器初始化"""
        self.assertIsInstance(self.video_recorder, FFmpegVideoRecorder)
        self.assertIsInstance(self.video_recorder.recording_streams, dict)
        self.assertIsInstance(self.video_recorder.temp_dirs, dict)
        self.assertEqual(self.video_recorder.buffer_seconds, 10)
        self.assertEqual(self.video_recorder.fps, 25)
    
    def test_get_recording_status(self):
        """测试获取录制状态"""
        stream_id = "test_stream_001"
        
        # 初始状态应该是不活跃
        status = self.video_recorder.get_recording_status(stream_id)
        
        self.assertIsInstance(status, dict)
        self.assertIn("status", status)
        self.assertEqual(status["status"], "not_recording")
        self.assertIn("message", status)
    
    def test_basic_attributes(self):
        """测试基本属性"""
        # 测试默认初始化值
        self.assertEqual(self.video_recorder.buffer_seconds, 10)
        self.assertEqual(self.video_recorder.fps, 25)
        
        # 测试自定义初始化
        custom_recorder = FFmpegVideoRecorder(buffer_seconds=30, fps=30)
        self.assertEqual(custom_recorder.buffer_seconds, 30)
        self.assertEqual(custom_recorder.fps, 30)
    
    def test_stop_stream_recording_not_exists(self):
        """测试停止不存在的流录制"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.video_recorder.stop_stream_recording("non_existent_stream")
            )
            
            # 应该返回False（流不存在）
            self.assertFalse(result)
        finally:
            loop.close()
    
    def test_get_available_segments_empty(self):
        """测试获取可用片段（空结果）"""
        stream_id = "test_stream_001"
        
        # 对于不存在的流，应该返回空列表
        segments = self.video_recorder.get_available_segments(stream_id)
        
        # 验证结果
        self.assertIsInstance(segments, list)
        self.assertEqual(len(segments), 0)
    
    def test_temp_dirs_management(self):
        """测试临时目录管理"""
        # 初始状态应该为空
        self.assertEqual(len(self.video_recorder.temp_dirs), 0)
        self.assertEqual(len(self.video_recorder.recording_streams), 0)


class TestFFmpegVideoRecorderUnit(unittest.TestCase):
    """FFmpeg视频录制器单元测试"""
    
    def test_multiple_instances(self):
        """测试多个实例"""
        recorder1 = FFmpegVideoRecorder(buffer_seconds=5, fps=20)
        recorder2 = FFmpegVideoRecorder(buffer_seconds=15, fps=30)
        
        self.assertEqual(recorder1.buffer_seconds, 5)
        self.assertEqual(recorder1.fps, 20)
        self.assertEqual(recorder2.buffer_seconds, 15)
        self.assertEqual(recorder2.fps, 30)
        
        # 实例应该是独立的
        self.assertNotEqual(id(recorder1), id(recorder2))


if __name__ == "__main__":
    unittest.main() 