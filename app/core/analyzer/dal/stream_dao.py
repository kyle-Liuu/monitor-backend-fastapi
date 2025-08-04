"""
流数据访问对象
- 提供对streams表的CRUD操作
- 处理JSON格式字段
"""

import json
from typing import Dict, List, Optional, Tuple
from .base import BaseDAO

class StreamDAO(BaseDAO):
    """流数据访问对象"""
    
    def get_stream_by_id(self, stream_id: str) -> Optional[Dict]:
        """根据ID获取流信息"""
        query = """
            SELECT stream_id, name, url, description, type, status, 
            error_message, enable_record, record_path, last_online_time,
            created_at, updated_at, consumers, frame_width, frame_height, fps
            FROM streams 
            WHERE stream_id = ?
        """
        results = self.execute_query(query, (stream_id,))
        if not results:
            return None
            
        # 处理JSON字段
        stream = results[0]
        if stream.get('consumers'):
            stream['consumers'] = json.loads(stream['consumers'])
        return stream
    
    def get_all_streams(self) -> List[Dict]:
        """获取所有流"""
        query = """
            SELECT stream_id, name, url, description, type, status, 
            error_message, enable_record, record_path, last_online_time,
            created_at, updated_at, consumers, frame_width, frame_height, fps
            FROM streams
        """
        results = self.execute_query(query)
        
        # 处理JSON字段
        for stream in results:
            if stream.get('consumers'):
                stream['consumers'] = json.loads(stream['consumers'])
        return results
    
    def add_stream(self, stream_data: Dict) -> bool:
        """添加流"""
        query = """
            INSERT INTO streams (stream_id, name, url, description, type, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            stream_data.get('stream_id'),
            stream_data.get('name'),
            stream_data.get('url'),
            stream_data.get('description'),
            stream_data.get('type', 'rtsp'),
            stream_data.get('status', 'offline')
        )
        return self.execute_insert(query, params) > 0
    
    def update_stream_status(self, stream_id: str, status: str, error_message: str = None) -> bool:
        """更新流状态"""
        if error_message:
            query = """
                UPDATE streams 
                SET status = ?, error_message = ?, last_online_time = CURRENT_TIMESTAMP 
                WHERE stream_id = ?
            """
            params = (status, error_message, stream_id)
        else:
            query = """
                UPDATE streams 
                SET status = ?, last_online_time = CURRENT_TIMESTAMP 
                WHERE stream_id = ?
            """
            params = (status, stream_id)
            
        return self.execute_update(query, params) > 0
    
    def delete_stream(self, stream_id: str) -> bool:
        """删除流"""
        query = "DELETE FROM streams WHERE stream_id = ?"
        return self.execute_update(query, (stream_id,)) > 0
        
    def update_consumers(self, stream_id: str, consumers: List[str]) -> bool:
        """更新消费者列表"""
        query = "UPDATE streams SET consumers = ? WHERE stream_id = ?"
        return self.execute_update(query, (json.dumps(consumers), stream_id)) > 0
    
    def update_stream_properties(self, stream_id: str, width: int, height: int, fps: float) -> bool:
        """更新流属性"""
        query = """
            UPDATE streams 
            SET frame_width = ?, frame_height = ?, fps = ? 
            WHERE stream_id = ?
        """
        return self.execute_update(query, (width, height, fps, stream_id)) > 0
    
    def stream_exists(self, stream_id: str) -> bool:
        """检查流是否存在"""
        query = "SELECT 1 FROM streams WHERE stream_id = ?"
        results = self.execute_query(query, (stream_id,))
        return len(results) > 0 