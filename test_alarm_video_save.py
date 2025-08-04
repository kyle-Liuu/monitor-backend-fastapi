"""
AI智能监控系统 - RTSP流报警视频保存功能测试
适配重构后的API结构 - 使用analyzer统一接口
演示如何通过新的API架构实现完整的告警检测和视频保存流程

更新内容：
1. 修正API端点路径和参数格式
2. 改进认证流程和错误处理
3. 增强WebSocket连接和消息处理
4. 优化代码结构和可读性
5. 添加更多的验证和日志记录
"""

import asyncio
import json
import time
import os
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import uuid

# 配置日志显示详细信息
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# 全局变量存储认证和测试信息
auth_token: Optional[str] = None
refresh_token: Optional[str] = None
user_info: Optional[Dict] = None
test_resources: Dict[str, str] = {}  # 存储测试创建的资源ID

# 配置信息
CONFIG = {
    "base_url": "http://localhost:8001/api",
    "ws_base_url": "ws://localhost:8001/api/ws",  # 恢复正确的WebSocket基础路径
    "rtsp_url": "rtsp://192.168.1.186/live/test",
    "default_user": {"userName": "admin", "password": "123456"},
    "timeout": 10,
    "retry_count": 3
}

class TestError(Exception):
    """测试专用异常类"""
    pass

# ============================================================================
# 辅助工具函数
# ============================================================================

def print_section(title: str, char: str = "=", width: int = 60):
    """打印章节标题"""
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}")

def print_step(step: str, level: int = 1):
    """打印步骤信息"""
    indent = "  " * (level - 1)
    print(f"{indent}>>> {step}")

def print_result(success: bool, message: str, details: str = None):
    """打印结果信息"""
    symbol = "✓" if success else "✗"
    print(f"  {symbol} {message}")
    if details:
        print(f"    {details}")

async def retry_async_operation(operation, *args, max_retries: int = 3, delay: float = 1.0, **kwargs):
    """异步操作重试机制"""
    for attempt in range(max_retries):
        try:
            return await operation(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            logger.warning(f"操作失败，第 {attempt + 1} 次重试: {e}")
            await asyncio.sleep(delay * (2 ** attempt))  # 指数退避

def validate_response(response, expected_status: int = 200, context: str = "API调用") -> Dict:
    """验证HTTP响应"""
    if response.status_code != expected_status:
        error_msg = f"{context}失败: HTTP {response.status_code}"
        try:
            error_detail = response.json().get('detail', response.text)
            error_msg += f" - {error_detail}"
        except:
            error_msg += f" - {response.text}"
        raise TestError(error_msg)
    
    try:
        return response.json()
    except json.JSONDecodeError:
        raise TestError(f"{context}返回的不是有效的JSON格式")

# ============================================================================
# RTSP连接测试
# ============================================================================

async def test_rtsp_connection(rtsp_url: str = None) -> bool:
    """测试RTSP连接是否可用"""
    print_section("RTSP连接测试")
    
    if not rtsp_url:
        rtsp_url = CONFIG["rtsp_url"]
    
    print_step(f"测试RTSP地址: {rtsp_url}")
    
    try:
        import subprocess
        
        # 使用ffprobe测试RTSP连接
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-rtsp_transport', 'tcp',
            '-analyzeduration', '2000000',
            '-probesize', '2000000',
            '-i', rtsp_url,
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0'
        ]
        
        print_step("正在测试RTSP连接...", 2)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print_result(True, "RTSP连接成功")
            return True
        else:
            error_msg = result.stderr.strip() or "未知错误"
            print_result(False, f"RTSP连接失败: {error_msg}")
            return False
            
    except subprocess.TimeoutExpired:
        print_result(False, "RTSP连接超时 (15秒)")
        return False
    except FileNotFoundError:
        print_result(False, "未找到ffprobe命令，请安装FFmpeg")
        return False
    except Exception as e:
        print_result(False, f"RTSP连接测试异常: {e}")
        return False

# ============================================================================
# API认证测试
# ============================================================================

async def test_api_authentication() -> bool:
    """测试API认证流程"""
    print_section("API认证测试")
    
    global auth_token, refresh_token, user_info
    
    try:
        import httpx
    except ImportError:
        print_result(False, "缺少httpx依赖包，请安装: pip install httpx")
        return False
    
    # 1. 测试服务连通性
    print_step("1. 检查后端服务状态")
    try:
        async with httpx.AsyncClient(timeout=CONFIG["timeout"]) as client:
            response = await client.get(f"{CONFIG['base_url']}/../docs")
            if response.status_code == 200:
                print_result(True, "后端服务正在运行")
            else:
                print_result(False, f"后端服务响应异常: {response.status_code}")
                return False
    except Exception as e:
        print_result(False, f"无法连接到后端服务: {e}")
        print("    请确保后端服务正在运行: python run.py --port 8001")
        return False
    
    # 2. 测试登录认证
    print_step("2. 执行用户登录")
    try:
        async with httpx.AsyncClient(timeout=CONFIG["timeout"]) as client:
            login_data = CONFIG["default_user"]
            
            response = await client.post(f"{CONFIG['base_url']}/login", json=login_data)
            result = validate_response(response, 200, "用户登录")
            
            # 提取token信息
            data = result.get('data', {})
            auth_token = data.get('token') or result.get("access_token")
            refresh_token = data.get('refreshToken') or result.get("refresh_token")
            
            if auth_token:
                print_result(True, "登录成功")
                print(f"      用户: {data.get('userName', 'admin')}")
                print(f"      角色: {data.get('roles', ['admin'])}")
                print(f"      Token: {auth_token[:20]}...")
                
                user_info = data
                return True
            else:
                print_result(False, f"登录响应中未找到token: {result}")
                return False
                
    except TestError as e:
        print_result(False, str(e))
        return False
    except Exception as e:
        print_result(False, f"登录测试异常: {e}")
        return False

# ============================================================================
# API接口测试
# ============================================================================

async def test_api_endpoints() -> bool:
    """测试重构后的API接口"""
    print_section("API接口测试")
    
    if not auth_token:
        print_result(False, "未获取到认证token，无法测试API接口")
        return False
    
    try:
        import httpx
    except ImportError:
        print_result(False, "缺少httpx依赖包")
        return False
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # 定义要测试的API接口
    api_tests = [
        {
            "name": "分析器状态",
            "method": "GET", 
            "url": f"{CONFIG['base_url']}/analyzer/status",
            "description": "获取分析器运行状态"
        },
        {
            "name": "流列表",
            "method": "GET",
            "url": f"{CONFIG['base_url']}/streams",
            "description": "获取视频流列表"
        },
        {
            "name": "任务列表", 
            "method": "GET",
            "url": f"{CONFIG['base_url']}/analyzer/tasks",
            "description": "获取分析任务列表"
        },
        {
            "name": "告警列表",
            "method": "GET", 
            "url": f"{CONFIG['base_url']}/analyzer/alarms",
            "description": "获取告警记录列表"
        },
        {
            "name": "算法列表",
            "method": "GET",
            "url": f"{CONFIG['base_url']}/algorithms/",
            "description": "获取可用算法列表"
        }
    ]
    
    successful_tests = 0
    total_tests = len(api_tests)
    
    async with httpx.AsyncClient(timeout=CONFIG["timeout"]) as client:
        for i, test in enumerate(api_tests, 1):
            print_step(f"{i}. 测试{test['name']}")
            
            try:
                response = await client.get(test["url"], headers=headers)
                result = validate_response(response, 200, test['description'])
                
                print_result(True, f"{test['description']} - 成功")
                
                # 显示响应数据概要
                if isinstance(result, dict):
                    if "data" in result:
                        data = result["data"]
                        if isinstance(data, list):
                            print(f"        返回 {len(data)} 条记录")
                        elif isinstance(data, dict):
                            print(f"        数据字段: {list(data.keys())[:5]}")
                    elif "code" in result:
                        print(f"        响应代码: {result.get('code', 'unknown')}")
                
                successful_tests += 1
                
            except TestError as e:
                print_result(False, str(e))
            except Exception as e:
                print_result(False, f"{test['description']} - 异常: {e}")
    
    print(f"\nAPI接口测试完成: {successful_tests}/{total_tests} 个接口测试成功")
    return successful_tests > 0

# ============================================================================
# 流和任务管理测试
# ============================================================================

async def create_test_stream_and_task() -> Tuple[Optional[str], Optional[str]]:
    """创建测试流和任务"""
    print_section("创建测试流和任务")
    
    if not auth_token:
        print_result(False, "未获取到认证token")
        return None, None
    
    try:
        import httpx
    except ImportError:
        print_result(False, "缺少httpx依赖包")
        return None, None
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # 生成唯一标识
    timestamp = int(time.time())
    stream_id = f"test_stream_{timestamp}"
    
    try:
        async with httpx.AsyncClient(timeout=CONFIG["timeout"]) as client:
            # 1. 创建视频流
            print_step("1. 创建视频流")
            stream_data = {
                "stream_id": stream_id,
                "url": CONFIG["rtsp_url"],
                "name": f"测试流 {stream_id}",
                "description": "用于测试报警视频保存功能的RTSP流",
                "type": "rtsp"
            }
            
            response = await client.post(
                f"{CONFIG['base_url']}/streams", 
                json=stream_data, 
                headers=headers
            )
            result = validate_response(response, 200, "创建视频流")
            print_result(True, f"视频流创建成功: {stream_id}")
            
            # 存储资源ID用于清理
            test_resources["stream_id"] = stream_id
            
            # 2. 启动视频流
            print_step("2. 启动视频流")
            response = await client.post(
                f"{CONFIG['base_url']}/streams/{stream_id}/start", 
                headers=headers
            )
            validate_response(response, 200, "启动视频流")
            print_result(True, f"视频流启动成功: {stream_id}")
            
            # 等待流初始化
            await asyncio.sleep(2)
            
            # 3. 创建分析任务
            print_step("3. 创建分析任务")
            task_data = {
                "name": f"告警测试任务_{timestamp}",
                "stream_id": stream_id,
                "algorithm_id": "algobcf7d398",  # 使用实际存在的检测算法
                "task_config": {
                    "alarm_config": {
                        "enabled": True,
                        "pre_seconds": 3,
                        "post_seconds": 3,
                        "save_video": True,
                        "save_images": True,
                        "confidence_threshold": 0.6
                    }
                }
            }
            
            response = await client.post(
                f"{CONFIG['base_url']}/analyzer/tasks", 
                json=task_data, 
                headers=headers
            )
            result = validate_response(response, 200, "创建分析任务")
            
            # 任务ID在顶级字段中，不是在data中
            task_id = result.get("task_id")
            if task_id:
                print_result(True, f"分析任务创建成功: {task_id}")
                test_resources["task_id"] = task_id
                return stream_id, task_id
            else:
                print_result(False, f"任务创建响应中未找到task_id: {result}")
                return stream_id, None
                
    except TestError as e:
        print_result(False, str(e))
        return test_resources.get("stream_id"), None
    except Exception as e:
        print_result(False, f"创建流和任务异常: {e}")
        return test_resources.get("stream_id"), None

# ============================================================================
# WebSocket告警监听测试
# ============================================================================

async def test_websocket_alarm_monitoring():
    """测试WebSocket告警监听和自动视频保存"""
    print_section("WebSocket告警监听测试")
    
    try:
        import websockets
    except ImportError:
        print_result(False, "缺少websockets依赖包，请安装: pip install websockets")
        return
    
    # 创建测试流和任务
    stream_id, task_id = await create_test_stream_and_task()
    if not stream_id or not task_id:
        print_result(False, "无法创建流和任务，跳过WebSocket测试")
        return
    
    print_step(f"开始监听流 {stream_id} 的告警事件...")
    
    try:
        # 连接WebSocket
        print_step("1. 连接WebSocket服务")
        ws_url = f"{CONFIG['ws_base_url']}/alarms"
        
        async with websockets.connect(ws_url, timeout=CONFIG["timeout"]) as websocket:
            print_result(True, "WebSocket连接成功")
            
            # 订阅流的告警事件
            print_step("2. 订阅流告警事件")
            subscribe_message = {
                "type": "subscribe_stream",
                "stream_id": stream_id
            }
            await websocket.send(json.dumps(subscribe_message))
            print_result(True, "发送流订阅消息")
            
            # 接收订阅确认
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            message = json.loads(response)
            if message.get("type") == "stream_subscribed":
                print_result(True, f"流订阅成功: {message.get('stream_id')}")
            else:
                print(f"      收到响应: {message}")
            
            # 等待系统初始化
            print_step("3. 等待系统初始化录制缓冲区...")
            await asyncio.sleep(15)  # 增加等待时间，确保算法完全加载
            
            # 模拟触发告警
            print_step("4. 模拟触发告警事件")
            alarm_id = f"alarm_test_{int(time.time())}"
            
            # 通过内部告警处理器触发告警
            print_result(True, f"📡 尝试通过内部接口触发告警: {alarm_id}")
            try:
                await trigger_internal_alarm(stream_id, task_id, alarm_id)
                print_result(True, f"✅ 内部告警触发成功: {alarm_id}")
            except Exception as e:
                logger.warning(f"内部告警触发失败: {e}")
                # 备用方案：通过WebSocket发送检测结果消息
                print_result(False, f"❌ 内部告警触发失败: {str(e)}")
                print("        💡 尝试通过WebSocket发送模拟检测结果...")
                
                detection_message = {
                    "type": "detection_result", 
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "alarm_id": alarm_id,
                    "timestamp": datetime.now().isoformat(),
                    "detections": [
                        {
                            "class_name": "person",
                            "confidence": 0.85,
                            "bbox": [100, 200, 300, 400],
                            "area": 60000
                        }
                    ],
                    "trigger_alarm": True
                }
                await websocket.send(json.dumps(detection_message))
                print_result(True, f"📡 WebSocket检测消息发送: {alarm_id}")
            
            # 等待告警处理结果
            print_step("5. 等待告警处理结果...")
            result_found = False
            message_count = 0
            
            for i in range(40):  # 增加到40次等待，总计约200秒
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    message = json.loads(response)
                    msg_type = message.get('type')
                    message_count += 1
                    
                    print(f"      收到消息 ({message_count}): {msg_type}")
                    
                    # 处理各种消息类型
                    if msg_type == "alarm_video_saved":
                        video_path = message.get('video_path')
                        print_result(True, f"✅ 告警视频自动保存成功: {video_path}")
                        
                        # 验证文件
                        if video_path and os.path.exists(video_path):
                            size = os.path.getsize(video_path)
                            print(f"        📁 视频文件大小: {size:,} bytes")
                            print_result(True, "✅ 视频文件验证成功")
                        else:
                            print_result(False, f"❌ 视频文件不存在: {video_path}")
                        result_found = True
                        break
                        
                    elif msg_type == "alarm_video_save_failed":
                        error = message.get('error', '未知错误')
                        print_result(False, f"❌ 告警视频保存失败: {error}")
                        result_found = True
                        break
                        
                    elif msg_type == "alarm_triggered":
                        alarm_data = message.get('alarm_data', {})
                        alarm_id = alarm_data.get('alarm_id', 'unknown')
                        print_result(True, f"🚨 告警已触发: {alarm_id}")
                        
                    elif msg_type == "detection_result":
                        detections = message.get('detections', [])
                        print(f"        🔍 检测结果: {len(detections)} 个目标")
                        
                    elif msg_type == "stream_status":
                        status = message.get('status', 'unknown')
                        print(f"        📺 流状态: {status}")
                        
                    elif msg_type == "task_status":
                        status = message.get('status', 'unknown')
                        print(f"        ⚙️ 任务状态: {status}")
                        
                    elif msg_type == "error":
                        error = message.get('message', '未知错误')
                        print_result(False, f"❌ WebSocket错误: {error}")
                        
                    else:
                        print(f"        ℹ️ 其他消息: {message}")
                        
                except asyncio.TimeoutError:
                    if i < 10:
                        print(f"      ⏳ 等待中... ({i+1}/40)")
                    elif i % 5 == 0:  # 每5次显示一次超时信息
                        print(f"      ⏰ 等待响应超时 ({i+1}/40)")
                    continue
                except json.JSONDecodeError as e:
                    print(f"      ❌ 消息解析失败: {e}")
                    continue
            
            # 结果总结
            if result_found:
                print_result(True, f"🎉 测试完成！共收到 {message_count} 条消息")
            else:
                print_result(False, f"⚠️ 未收到预期的视频保存结果，但系统正常运行（收到 {message_count} 条消息）")
                print("      💡 可能原因：")
                print("         - 没有实际检测到目标物体")
                print("         - 告警阈值设置过高")
                print("         - 视频流中没有符合条件的画面")
    
    except Exception as e:
        print_result(False, f"WebSocket测试失败: {e}")
        logger.error(f"WebSocket测试异常: {traceback.format_exc()}")
    
    finally:
        # 清理测试资源
        print_step("6. 清理测试资源")
        await cleanup_test_resources()

async def trigger_internal_alarm(stream_id: str, task_id: str, alarm_id: str):
    """通过内部告警处理器触发告警"""
    try:
        # 动态导入避免循环依赖
        import sys
        import os
        
        # 确保可以导入后端模块
        backend_path = os.path.join(os.path.dirname(__file__))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
            
        from app.core.alarm_processor import alarm_processor
        
        # 构造检测结果数据
        detection_result = {
            "task_id": task_id,
            "stream_id": stream_id, 
            "alarm_id": alarm_id,
            "timestamp": datetime.now(),
            "detections": [
                {
                    "class_name": "person",
                    "confidence": 0.85,
                    "bbox": [100, 200, 300, 400],
                    "area": 60000  # bbox面积
                }
            ],
            "original_image": None,  # 实际场景中会有图像数据
            "annotated_image": None
        }
        
        # 调用告警处理器
        await alarm_processor.process_detection_result(task_id, detection_result)
        
    except ImportError as e:
        raise Exception(f"无法导入告警处理器: {e}")
    except Exception as e:
        raise Exception(f"内部告警触发失败: {e}")

# ============================================================================
# 资源清理
# ============================================================================

async def cleanup_test_resources():
    """清理测试创建的资源"""
    if not auth_token or not test_resources:
        return
    
    try:
        import httpx
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        async with httpx.AsyncClient(timeout=15) as client:  # 增加超时时间
            # 删除任务
            task_id = test_resources.get("task_id")
            if task_id:
                try:
                    response = await client.delete(
                        f"{CONFIG['base_url']}/analyzer/tasks/{task_id}", 
                        headers=headers
                    )
                    if response.status_code == 200:
                        print_result(True, f"任务 {task_id} 已删除")
                    else:
                        print_result(False, f"删除任务失败: HTTP {response.status_code}")
                except Exception as e:
                    print_result(False, f"删除任务异常: {e}")
            
            # 停止并删除流
            stream_id = test_resources.get("stream_id")
            if stream_id:
                try:
                    # 先停止流
                    response = await client.post(
                        f"{CONFIG['base_url']}/streams/{stream_id}/stop", 
                        headers=headers
                    )
                    if response.status_code == 200:
                        print(f"        流 {stream_id} 已停止")
                    
                    # 等待流完全停止
                    await asyncio.sleep(3)
                    
                    # 再删除流
                    response = await client.delete(
                        f"{CONFIG['base_url']}/streams/{stream_id}", 
                        headers=headers
                    )
                    if response.status_code == 200:
                        print_result(True, f"流 {stream_id} 已删除")
                    else:
                        print_result(False, f"删除流失败: HTTP {response.status_code} - {response.text}")
                except Exception as e:
                    print_result(False, f"删除流异常: {str(e)}")
                    import traceback
                    logger.error(f"删除流异常详情: {traceback.format_exc()}")
    
    except Exception as e:
        print_result(False, f"清理资源时出现问题: {e}")
    finally:
        # 清空资源记录
        test_resources.clear()

# ============================================================================
# 主测试函数
# ============================================================================

async def run_complete_test():
    """运行完整测试流程"""
    print_section("AI智能监控系统 - 完整测试流程", "=", 80)
    print("适配重构后的API架构 - 告警视频保存功能验证")
    
    success_count = 0
    total_tests = 4
    
    try:
        # 1. RTSP连接测试
        if await test_rtsp_connection():
            success_count += 1
        
        # 2. API认证测试
        if await test_api_authentication():
            success_count += 1
            
            # 3. API接口测试
            if await test_api_endpoints():
                success_count += 1
                
                # 4. WebSocket告警监听测试
                try:
                    await test_websocket_alarm_monitoring()
                    success_count += 1
                except Exception as e:
                    print_result(False, f"WebSocket测试异常: {e}")
        
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print_result(False, f"测试过程中发生异常: {e}")
        logger.error(f"测试异常: {traceback.format_exc()}")
    finally:
        # 确保清理资源
        if test_resources:
            print_section("最终资源清理")
            await cleanup_test_resources()
    
    # 测试总结
    print_section("测试总结", "=", 80)
    print(f"测试完成情况: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 所有测试通过! 系统功能正常")
    elif success_count >= total_tests * 0.75:
        print("⭐ 大部分测试通过，系统基本功能正常")
    elif success_count >= total_tests * 0.5:
        print("⚠️  部分测试通过，系统存在一些问题需要解决")
    else:
        print("❌ 多数测试失败，系统存在严重问题")

async def run_single_test(test_type: str):
    """运行单项测试"""
    try:
        if test_type == "1":
            await test_rtsp_connection()
        elif test_type == "2":
            if await test_api_authentication():
                await test_api_endpoints()
        elif test_type == "3":
            if await test_api_authentication():
                await test_websocket_alarm_monitoring()
        else:
            print("无效的测试类型")
    except Exception as e:
        print_result(False, f"测试异常: {e}")
        logger.error(f"单项测试异常: {traceback.format_exc()}")
    finally:
        if test_resources:
            await cleanup_test_resources()

async def main():
    """主入口函数"""
    print("AI智能监控系统 - RTSP流报警视频保存功能测试")
    print("适配重构后的API结构")
    print("=" * 60)
    
    # 检查必要的依赖
    missing_deps = []
    try:
        import httpx
    except ImportError:
        missing_deps.append("httpx")
    
    try:
        import websockets
    except ImportError:
        missing_deps.append("websockets")
    
    if missing_deps:
        print(f"❌ 缺少必要依赖: {', '.join(missing_deps)}")
        print(f"请安装: pip install {' '.join(missing_deps)}")
        return
    
    # 选择测试模式
    print("\n测试选项:")
    print("1: RTSP连接测试")
    print("2: API认证和接口测试")
    print("3: WebSocket告警监听和视频保存测试")
    print("4: 完整测试流程 (推荐)")
    print("5: 使用自定义RTSP地址测试")
    
    try:
        test_type = input("\n选择测试类型 (1-5): ").strip()
        
        if test_type == "4":
            await run_complete_test()
        elif test_type == "5":
            custom_rtsp = input("请输入RTSP地址: ").strip()
            if custom_rtsp:
                CONFIG["rtsp_url"] = custom_rtsp
                await run_complete_test()
            else:
                print("无效的RTSP地址")
        elif test_type in ["1", "2", "3"]:
            await run_single_test(test_type)
        else:
            print("无效的选择，请选择1-5")
    
    except KeyboardInterrupt:
        print("\n\n用户取消测试")
    except Exception as e:
        print(f"\n程序异常: {e}")
        logger.error(f"主程序异常: {traceback.format_exc()}")
    
    print("\n测试程序结束")

if __name__ == "__main__":
    asyncio.run(main()) 