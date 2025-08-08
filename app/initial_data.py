import logging
import json
import os
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User, VideoStream, Algorithm, Task, BlacklistedToken, Menu, ModelInstance, SystemConfig
from app.core.security import get_password_hash

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_unique_id(prefix=""):
    """生成唯一ID"""
    unique_id = f"{prefix}{uuid.uuid4().hex[:8]}"
    return unique_id


def create_initial_users(db: Session) -> None:
    """
    创建初始用户
    """
    # 检查是否已存在管理员
    result = db.execute(select(User).where(User.username == "super")).scalars().first()
    if result:
        logger.info("超级管理员用户已存在，跳过创建")
        return
    
    # 创建超级管理员
    super_admin = User(
        id=generate_unique_id("user"),
        username="super",
        email="super@example.com",
        hashed_password=get_password_hash("123456"),
        full_name="超级管理员",
        avatar="/assets/avatar/super_admin.webp",
        is_active=True,
        role="R_SUPER"
    )
    db.add(super_admin)
    
    # 创建管理员
    admin_user = User(
        id=generate_unique_id("user"),
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("123456"),
        full_name="管理员",
        avatar="/assets/avatar/admin.webp",
        is_active=True,
        role="R_ADMIN"
    )
    db.add(admin_user)
    
    # 创建普通用户
    normal_user = User(
        id=generate_unique_id("user"),
        username="user",
        email="user@example.com",
        hashed_password=get_password_hash("123456"),
        full_name="普通用户",
        avatar="/assets/avatar/user.webp",
        is_active=True,
        role="R_USER"
    )
    db.add(normal_user)
    
    db.commit()
    logger.info("初始用户创建成功")


def create_initial_roles(db: Session) -> None:
    """
    创建初始角色数据
    """
    from app.db.models import Role
    from app.utils.utils import generate_unique_id
    
    # 检查是否已存在角色
    result = db.execute(select(Role).limit(1)).scalars().first()
    if result:
        logger.info("角色数据已存在，跳过创建")
        return
    
    # 创建超级管理员角色
    super_role = Role(
        role_id=generate_unique_id("role"),
        role_code="R_SUPER",
        role_name="超级管理员",
        description="拥有系统全部权限",
        is_enabled=True
    )
    db.add(super_role)
    
    # 创建管理员角色
    admin_role = Role(
        role_id=generate_unique_id("role"),
        role_code="R_ADMIN",
        role_name="管理员",
        description="拥有业务管理权限",
        is_enabled=True
    )
    db.add(admin_role)
    
    # 创建普通用户角色
    user_role = Role(
        role_id=generate_unique_id("role"),
        role_code="R_USER",
        role_name="普通用户",
        description="基础查看权限",
        is_enabled=True
    )
    db.add(user_role)
    
    db.commit()
    logger.info("初始角色创建成功")


def create_initial_organizations(db: Session) -> None:
    """
    创建初始组织数据
    """
    from app.db.models import Organization
    from app.utils.utils import generate_unique_id
    
    # 检查是否已存在组织
    result = db.execute(select(Organization).limit(1)).scalars().first()
    if result:
        logger.info("组织数据已存在，跳过创建")
        return
    
    # 创建根组织
    root_org = Organization(
        org_id=generate_unique_id("org"),
        name="总部",
        path="/1/",
        description="公司总部",
        status="active",
        sort_order=1
    )
    db.add(root_org)
    
    # 创建子组织
    building_a = Organization(
        org_id=generate_unique_id("org"),
        name="A栋",
        parent_id=root_org.org_id,
        path=f"/1/{root_org.org_id}/",
        description="A栋办公楼",
        status="active",
        sort_order=1
    )
    db.add(building_a)
    
    building_b = Organization(
        org_id=generate_unique_id("org"),
        name="B栋",
        parent_id=root_org.org_id,
        path=f"/1/{root_org.org_id}/",
        description="B栋办公楼",
        status="active",
        sort_order=2
    )
    db.add(building_b)
    
    db.commit()
    logger.info("初始组织创建成功")


def create_initial_streams(db: Session) -> None:
    """
    创建初始视频流数据
    """
    # 检查是否已存在流
    result = db.execute(select(VideoStream).limit(1)).scalars().first()
    if result:
        logger.info("视频流数据已存在，跳过创建")
        return

    # 测试视频文件路径
    test_video_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bus.jpg")
    test_video_path_norm = os.path.normpath(test_video_path)
    
    # 创建示例视频流
    stream1 = VideoStream(
        stream_id=generate_unique_id("stream"),
        name="测试视频-公交车",
        url=test_video_path_norm,
        description="用于算法测试的样例视频-公交车",
        stream_type="file",
        status="inactive",
        frame_width=1920,
        frame_height=1080,
        fps=25.0,
        consumer_count=0
    )
    db.add(stream1)
    
    # 创建RTSP测试流
    stream2 = VideoStream(
        stream_id=generate_unique_id("stream"),
        name="RTSP测试流",
        url="rtsp://192.168.1.186/live/test",
        description="RTSP测试流，用于演示",
        stream_type="rtsp",
        status="inactive",
        consumer_count=0
    )
    db.add(stream2)
    
    # 创建HTTP测试流
    stream3 = VideoStream(
        stream_id=generate_unique_id("stream"),
        name="HTTP测试流",
        url="http://localhost:8080/stream",
        description="HTTP测试流，用于演示",
        stream_type="http",
        status="inactive",
        consumer_count=0
    )
    db.add(stream3)
    
    db.commit()
    logger.info("初始视频流数据创建成功")


def create_initial_algorithms(db: Session) -> None:
    """
    创建初始算法数据
    """
    # 检查是否已存在算法
    result = db.execute(select(Algorithm).limit(1)).scalars().first()
    if result:
        logger.info("算法数据已存在，跳过创建")
        return
    
    # 创建YOLOv8检测算法
    yolov8_config = {
        "name": "yolov8n", 
        "version": "1.0.0",
        "device": "cpu",
        "confidence_threshold": 0.5,
        "nms_threshold": 0.4,
        "classes": ["person", "car", "truck", "bus", "motorcycle"],
        "model_path": "algorithms.installed.algocf6c488d.model.simple_yolo",
        "postprocessor_path": "algorithms.installed.algocf6c488d.postprocessor.simple_postprocessor"
    }
    
    algorithm1 = Algorithm(
        algo_id=generate_unique_id("algo"),
        name="YOLOv8目标检测",
        description="基于YOLOv8的目标检测算法，支持多种目标识别",
        package_name="algorithms.installed.algocf6c488d",  # 修改为实际存在的算法包
        algorithm_type="detection",
        version="1.0.0",
        config=json.dumps(yolov8_config),
        status="active",  # 改为active状态
        model_path="algorithms/installed/algocf6c488d/model/yolov8_model/yolov8n.pt",
        max_instances=3,
        current_instances=0,
        device_type="cpu"
    )
    db.add(algorithm1)
    
    # 创建人脸检测算法 - 使用相同的YOLOv8算法包但配置不同
    face_config = {
        "name": "face_detection",
        "version": "1.0.0", 
        "device": "cpu",
        "confidence_threshold": 0.7,
        "classes": ["person"],  # YOLOv8可以检测person类别作为人脸检测
        "model_path": "algorithms.installed.algocf6c488d.model.simple_yolo",
        "postprocessor_path": "algorithms.installed.algocf6c488d.postprocessor.simple_postprocessor"
    }
    
    algorithm2 = Algorithm(
        algo_id=generate_unique_id("algo"),
        name="人脸检测",
        description="专门用于人脸检测的算法",
        package_name="algorithms.installed.algocf6c488d",  # 修改为实际存在的算法包
        algorithm_type="detection",
        version="1.0.0",
        config=json.dumps(face_config),
        status="active",  # 改为active状态
        max_instances=2,
        current_instances=0,
        device_type="cpu"
    )
    db.add(algorithm2)
    
    # 创建车辆检测算法 - 使用相同的YOLOv8算法包但配置不同
    vehicle_config = {
        "name": "vehicle_detection",
        "version": "1.0.0",
        "device": "cpu", 
        "confidence_threshold": 0.6,
        "classes": ["car", "truck", "bus", "motorcycle"],
        "model_path": "algorithms.installed.algocf6c488d.model.simple_yolo",
        "postprocessor_path": "algorithms.installed.algocf6c488d.postprocessor.simple_postprocessor"
    }
    
    algorithm3 = Algorithm(
        algo_id=generate_unique_id("algo"),
        name="车辆检测",
        description="专门用于车辆检测的算法",
        package_name="algorithms.installed.algocf6c488d",  # 修改为实际存在的算法包
        algorithm_type="detection",
        version="1.0.0",
        config=json.dumps(vehicle_config),
        status="active",  # 改为active状态
        max_instances=2,
        current_instances=0,
        device_type="cpu"
    )
    db.add(algorithm3)
    
    db.commit()
    logger.info("初始算法数据创建成功")


def create_initial_model_instances(db: Session) -> None:
    """
    创建初始模型实例数据
    """
    # 检查是否已存在模型实例
    result = db.execute(select(ModelInstance).limit(1)).scalars().first()
    if result:
        logger.info("模型实例数据已存在，跳过创建")
        return

    # 获取算法ID
    algorithms = db.execute(select(Algorithm)).scalars().all()
    
    for algorithm in algorithms:
        # 为每个算法创建一个默认实例
        instance = ModelInstance(
            instance_id=generate_unique_id("instance"),
            algorithm_id=algorithm.algo_id,
            instance_name=f"{algorithm.name}_instance_1",
            status="idle",
            device_type=algorithm.device_type,
            use_count=0
        )
        db.add(instance)
    
    db.commit()
    logger.info("初始模型实例数据创建成功")


def create_initial_system_configs(db: Session) -> None:
    """
    创建初始系统配置数据
    """
    # 检查是否已存在系统配置
    result = db.execute(select(SystemConfig).limit(1)).scalars().first()
    if result:
        logger.info("系统配置数据已存在，跳过创建")
        return

    # 系统配置列表
    system_configs = [
        {
            "config_key": "max_stream_consumers",
            "config_value": "5",
            "config_type": "int",
            "description": "单个视频流最大消费者数量"
        },
        {
            "config_key": "max_model_instances",
            "config_value": "3",
            "config_type": "int",
            "description": "单个算法最大模型实例数"
        },
        {
            "config_key": "frame_buffer_size",
            "config_value": "30",
            "config_type": "int",
            "description": "帧缓冲区大小"
        },
        {
            "config_key": "default_fps",
            "config_value": "25.0",
            "config_type": "float",
            "description": "默认帧率"
        },
        {
            "config_key": "enable_auto_cleanup",
            "config_value": "true",
            "config_type": "bool",
            "description": "是否启用自动清理"
        },
        {
            "config_key": "cleanup_interval",
            "config_value": "3600",
            "config_type": "int",
            "description": "清理间隔（秒）"
        },
        {
            "config_key": "max_alarm_history",
            "config_value": "1000",
            "config_type": "int",
            "description": "最大告警历史记录数"
        },
        {
            "config_key": "enable_event_bus",
            "config_value": "true",
            "config_type": "bool",
            "description": "是否启用事件总线"
        },
        {
            "config_key": "event_bus_threads",
            "config_value": "4",
            "config_type": "int",
            "description": "事件总线线程数"
        },
        {
            "config_key": "database_connection_pool_size",
            "config_value": "10",
            "config_type": "int",
            "description": "数据库连接池大小"
        }
    ]
    
    for config in system_configs:
        system_config = SystemConfig(
            config_id=generate_unique_id("config"),
            config_key=config["config_key"],
            config_value=config["config_value"],
            config_type=config["config_type"],
            description=config["description"],
            is_system=True
        )
        db.add(system_config)
    
    db.commit()
    logger.info("初始系统配置数据创建成功")


def create_initial_menus(db: Session) -> None:
    """
    创建初始菜单数据
    """
    # 检查是否已存在菜单
    result = db.execute(select(Menu).limit(1)).scalars().first()
    if result:
        logger.info("菜单数据已存在，跳过创建")
        return

    # 创建菜单数据
    # 基于前端 asyncRoutes.ts 创建菜单数据
    dashboard_id = generate_unique_id("menu")
        # 监控菜单
    monitor_menu = Menu(
        menu_id=generate_unique_id("menu"),
        name="Monitor",
        path="/monitor",
        component="/monitor",
        meta_title="menus.monitor.title",
        meta_icon="&#xe8ba;",
        sort=1,
        keep_alive=True,
        is_full_page=True
    )
    db.add(monitor_menu)
    
    
    # 创建Dashboard主菜单
    dashboard = Menu(
        menu_id=dashboard_id,
        name="Dashboard",
        path="/dashboard",
        component="/index/index",
        meta_title="menus.dashboard.title",
        meta_icon="&#xe721;",
        sort=2,
        keep_alive=True
    )
    db.add(dashboard)
    
    # Dashboard子菜单
    dashboard_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Console",
            path="console",
            component="/dashboard/console",
            meta_title="menus.dashboard.console",
            meta_icon="",
            parent_id=dashboard_id,
            sort=1,
            keep_alive=False
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Analysis",
            path="analysis",
            component="/dashboard/analysis",
            meta_title="menus.dashboard.analysis",
            meta_icon="",
            parent_id=dashboard_id,
            sort=2,
            keep_alive=False
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Ecommerce",
            path="ecommerce",
            component="/dashboard/ecommerce",
            meta_title="menus.dashboard.ecommerce",
            meta_icon="",
            parent_id=dashboard_id,
            sort=3,
            keep_alive=False
        )
    ]
    for menu in dashboard_children:
        db.add(menu)
    
    # 模板菜单
    template_id = generate_unique_id("menu")
    template_menu = Menu(
        menu_id=template_id,
        name="Template",
        path="/template",
        component="/index/index",
        meta_title="menus.template.title",
        meta_icon="&#xe860;",
        sort=3,
        keep_alive=True
    )
    db.add(template_menu)
    
    # 模板子菜单
    template_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Cards",
            path="cards",
            component="/template/cards",
            meta_title="menus.template.cards",
            meta_icon="",
            parent_id=template_id,
            sort=1,
            keep_alive=False
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Banners",
            path="banners",
            component="/template/banners",
            meta_title="menus.template.banners",
            meta_icon="",
            parent_id=template_id,
            sort=2,
            keep_alive=False
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Charts",
            path="charts",
            component="/template/charts",
            meta_title="menus.template.charts",
            meta_icon="",
            parent_id=template_id,
            sort=3,
            keep_alive=False
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Map",
            path="map",
            component="/template/map",
            meta_title="menus.template.map",
            meta_icon="",
            parent_id=template_id,
            sort=4,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Chat",
            path="chat",
            component="/template/chat",
            meta_title="menus.template.chat",
            meta_icon="",
            parent_id=template_id,
            sort=5,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Calendar",
            path="calendar",
            component="/template/calendar",
            meta_title="menus.template.calendar",
            meta_icon="",
            parent_id=template_id,
            sort=6,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Pricing",
            path="pricing",
            component="/template/pricing",
            meta_title="menus.template.pricing",
            meta_icon="",
            parent_id=template_id,
            sort=7,
            keep_alive=True,
            is_hidden=False,
            is_full_page=True
        )
    ]
    for menu in template_children:
        db.add(menu)
    
    # Widgets菜单
    widgets_id = generate_unique_id("menu")
    widgets_menu = Menu(
        menu_id=widgets_id,
        name="Widgets",
        path="/widgets",
        component="/index/index",
        meta_title="menus.widgets.title",
        meta_icon="&#xe81a;",
        sort=4,
        keep_alive=True
    )
    db.add(widgets_menu)
    
    # Widgets子菜单
    widgets_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="IconList",
            path="icon-list",
            component="/widgets/icon-list",
            meta_title="menus.widgets.iconList",
            meta_icon="",
            parent_id=widgets_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="IconSelector",
            path="icon-selector",
            component="/widgets/icon-selector",
            meta_title="menus.widgets.iconSelector",
            meta_icon="",
            parent_id=widgets_id,
            sort=2,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ImageCrop",
            path="image-crop",
            component="/widgets/image-crop",
            meta_title="menus.widgets.imageCrop",
            meta_icon="",
            parent_id=widgets_id,
            sort=3,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Excel",
            path="excel",
            component="/widgets/excel",
            meta_title="menus.widgets.excel",
            meta_icon="",
            parent_id=widgets_id,
            sort=4,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="CountTo",
            path="count-to",
            component="/widgets/count-to",
            meta_title="menus.widgets.countTo",
            meta_icon="",
            parent_id=widgets_id,
            sort=5,
            keep_alive=False
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Qrcode",
            path="qrcode",
            component="/widgets/qrcode",
            meta_title="menus.widgets.qrcode",
            meta_icon="",
            parent_id=widgets_id,
            sort=6,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Drag",
            path="drag",
            component="/widgets/drag",
            meta_title="menus.widgets.drag",
            meta_icon="",
            parent_id=widgets_id,
            sort=7,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="TextScroll",
            path="text-scroll",
            component="/widgets/text-scroll",
            meta_title="menus.widgets.textScroll",
            meta_icon="",
            parent_id=widgets_id,
            sort=8,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Fireworks",
            path="fireworks",
            component="/widgets/fireworks",
            meta_title="menus.widgets.fireworks",
            meta_icon="",
            parent_id=widgets_id,
            sort=9,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ElementUI",
            path="/outside/iframe/elementui",
            component="",
            meta_title="menus.widgets.elementUI",
            meta_icon="",
            parent_id=widgets_id,
            sort=10,
            keep_alive=False,
            is_iframe=True,
            link="https://element-plus.org/zh-CN/component/overview.html",
            show_badge=True
        )
    ]
    for menu in widgets_children:
        db.add(menu)
    
    # Examples菜单
    examples_id = generate_unique_id("menu")
    examples_menu = Menu(
        menu_id=examples_id,
        name="Examples",
        path="/examples",
        component="/index/index",
        meta_title="menus.examples.title",
        meta_icon="&#xe8d4;",
        sort=5,
        keep_alive=True
    )
    db.add(examples_menu)
    
    # Examples子菜单
    examples_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Tabs",
            path="tabs",
            component="/examples/tabs",
            meta_title="menus.examples.tabs",
            meta_icon="",
            parent_id=examples_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="TablesBasic",
            path="tables/basic",
            component="/examples/tables/basic",
            meta_title="menus.examples.tablesBasic",
            meta_icon="",
            parent_id=examples_id,
            sort=2,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Tables",
            path="tables",
            component="/examples/tables",
            meta_title="menus.examples.tables",
            meta_icon="",
            parent_id=examples_id,
            sort=3,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="TablesTree",
            path="tables/tree",
            component="/examples/tables/tree",
            meta_title="menus.examples.tablesTree",
            meta_icon="",
            parent_id=examples_id,
            sort=4,
            keep_alive=True
        )
    ]
    for menu in examples_children:
        db.add(menu)
    
    # 系统管理菜单
    system_id = generate_unique_id("menu")
    system_menu = Menu(
        menu_id=system_id,
        name="System",
        path="/system",
        component="/index/index",
        meta_title="menus.system.title",
        meta_icon="&#xe7b9;",
        sort=6,
        roles="R_SUPER,R_ADMIN",
        keep_alive=True
    )
    db.add(system_menu)
    
    # 系统管理子菜单
    system_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="User",
            path="user",
            component="/system/user",
            meta_title="menus.system.user",
            meta_icon="",
            parent_id=system_id,
            sort=1,
            roles="R_SUPER,R_ADMIN",
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Role",
            path="role",
            component="/system/role",
            meta_title="menus.system.role",
            meta_icon="",
            parent_id=system_id,
            sort=2,
            roles="R_SUPER",
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="UserCenter",
            path="user-center",
            component="/system/user-center",
            meta_title="menus.system.userCenter",
            meta_icon="",
            parent_id=system_id,
            sort=3,
            is_hidden=True,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Menus",
            path="menu",
            component="/system/menu",
            meta_title="menus.system.menu",
            meta_icon="",
            parent_id=system_id,
            sort=4,
            roles="R_SUPER",
            keep_alive=True,
            # 添加按钮权限列表
            auth_list=json.dumps([
                {"title": "添加", "authMark": "add"},
                {"title": "编辑", "authMark": "edit"},
                {"title": "删除", "authMark": "delete"}
            ])
        )
    ]
    for menu in system_children:
        db.add(menu)
        
    # 文章管理菜单
    article_id = generate_unique_id("menu")
    article_menu = Menu(
        menu_id=article_id,
        name="Article",
        path="/article",
        component="/index/index",
        meta_title="menus.article.title",
        meta_icon="&#xe7ae;",
        sort=7,
        roles="R_SUPER,R_ADMIN",
        keep_alive=True
    )
    db.add(article_menu)
    
    # 文章管理子菜单
    article_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ArticleList",
            path="article-list",
            component="/article/list",
            meta_title="menus.article.articleList",
            meta_icon="",
            parent_id=article_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ArticleDetail",
            path="detail",
            component="/article/detail",
            meta_title="menus.article.articleDetail",
            meta_icon="",
            parent_id=article_id,
            sort=2,
            is_hidden=True,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ArticleComment",
            path="comment",
            component="/article/comment",
            meta_title="menus.article.comment",
            meta_icon="",
            parent_id=article_id,
            sort=3,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ArticlePublish",
            path="publish",
            component="/article/publish",
            meta_title="menus.article.articlePublish",
            meta_icon="",
            parent_id=article_id,
            sort=4,
            keep_alive=True
        )
    ]
    for menu in article_children:
        db.add(menu)
    
    # 结果页菜单
    result_id = generate_unique_id("menu")
    result_menu = Menu(
        menu_id=result_id,
        name="Result",
        path="/result",
        component="/index/index",
        meta_title="menus.result.title",
        meta_icon="&#xe715;",
        sort=8,
        keep_alive=True
    )
    db.add(result_menu)
    
    # 结果页子菜单
    result_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ResultSuccess",
            path="success",
            component="/result/success",
            meta_title="menus.result.success",
            meta_icon="",
            parent_id=result_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="ResultFail",
            path="fail",
            component="/result/fail",
            meta_title="menus.result.fail",
            meta_icon="",
            parent_id=result_id,
            sort=2,
            keep_alive=True
        )
    ]
    for menu in result_children:
        db.add(menu)
    
    # 异常页菜单
    exception_id = generate_unique_id("menu")
    exception_menu = Menu(
        menu_id=exception_id,
        name="Exception",
        path="/exception",
        component="/index/index",
        meta_title="menus.exception.title",
        meta_icon="&#xe820;",
        sort=9,
        keep_alive=True
    )
    db.add(exception_menu)
    
    # 异常页子菜单
    exception_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="403",
            path="403",
            component="/exception/403",
            meta_title="menus.exception.forbidden",
            meta_icon="",
            parent_id=exception_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="404",
            path="404",
            component="/exception/404",
            meta_title="menus.exception.notFound",
            meta_icon="",
            parent_id=exception_id,
            sort=2,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="500",
            path="500",
            component="/exception/500",
            meta_title="menus.exception.serverError",
            meta_icon="",
            parent_id=exception_id,
            sort=3,
            keep_alive=True
        )
    ]
    for menu in exception_children:
        db.add(menu)
    
    # 安全防护菜单
    safeguard_id = generate_unique_id("menu")
    safeguard_menu = Menu(
        menu_id=safeguard_id,
        name="Safeguard",
        path="/safeguard",
        component="/index/index",
        meta_title="menus.safeguard.title",
        meta_icon="&#xe816;",
        sort=10,
        keep_alive=False
    )
    db.add(safeguard_menu)
    
    # 安全防护子菜单
    safeguard_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="SafeguardServer",
            path="server",
            component="/safeguard/server",
            meta_title="menus.safeguard.server",
            meta_icon="",
            parent_id=safeguard_id,
            sort=1,
            keep_alive=True
        )
    ]
    for menu in safeguard_children:
        db.add(menu)
    
    # 帮助菜单
    help_id = generate_unique_id("menu")
    help_menu = Menu(
        menu_id=help_id,
        name="Help",
        path="/help",
        component="/index/index",
        meta_title="menus.help.title",
        meta_icon="&#xe719;",
        sort=11,
        keep_alive=False
    )
    db.add(help_menu)
    
    # 更新日志菜单
    changelog_menu = Menu(
        menu_id=generate_unique_id("menu"),
        name="ChangeLog",
        path="/change/log",
        component="/change/log",
        meta_title="menus.plan.log",
        meta_icon="&#xe712;",
        sort=12,
        keep_alive=False
    )
    db.add(changelog_menu)
    
    # 警告菜单
    warning_id = generate_unique_id("menu")
    warning_menu = Menu(
        menu_id=warning_id,
        name="Warning",
        path="/warning",
        component="/index/index",
        meta_title="menus.warning.title",
        meta_icon="&#xe8b2;",
        sort=13,
        keep_alive=True
    )
    db.add(warning_menu)
    
    # 警告子菜单
    warning_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="WarningInfo",
            path="warninginfo",
            component="/warning/warninginfo",
            meta_title="menus.warning.info",
            meta_icon="",
            parent_id=warning_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="DataPush",
            path="datapush",
            component="/warning/datapush",
            meta_title="menus.warning.datapush",
            meta_icon="",
            parent_id=warning_id,
            sort=2,
            keep_alive=True
        )
    ]
    for menu in warning_children:
        db.add(menu)
    
    # 视频流管理菜单
    video_id = generate_unique_id("menu")
    video_menu = Menu(
        menu_id=video_id,
        name="VideoStream",
        path="/videostream",
        component="/index/index",
        meta_title="menus.videostream.title",
        meta_icon="&#xe8b3;",
        sort=14,
        keep_alive=True
    )
    db.add(video_menu)
    
    # 视频流管理子菜单
    video_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="StreamInfo",
            path="streaminfo",
            component="/videostream/streaminfo",
            meta_title="menus.videostream.streaminfo",
            meta_icon="",
            parent_id=video_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="VirtualBinding",
            path="virtualbinding",
            component="/videostream/virtualbinding",
            meta_title="menus.videostream.virtualbinding",
            meta_icon="",
            parent_id=video_id,
            sort=2,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="Organization",
            path="organization",
            component="/videostream/organization",
            meta_title="menus.videostream.organization",
            meta_icon="",
            parent_id=video_id,
            sort=3,
            keep_alive=True
        )
    ]
    for menu in video_children:
        db.add(menu)
    
    # 算法管理菜单
    algo_id = generate_unique_id("menu")
    algo_menu = Menu(
        menu_id=algo_id,
        name="Algorithm",
        path="/algorithm",
        component="/index/index",
        meta_title="menus.algorithm.title",
        meta_icon="&#xe8b4;",
        sort=15,
        keep_alive=True
    )
    db.add(algo_menu)
    
    # 算法管理子菜单
    algo_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="AlgorithmInfo",
            path="info",
            component="/algorithm/algoinfo",
            meta_title="menus.algorithm.info",
            meta_icon="",
            parent_id=algo_id,
            sort=1,
            keep_alive=True
        )
    ]
    for menu in algo_children:
        db.add(menu)
    
    # 资源库菜单
    repo_id = generate_unique_id("menu")
    repo_menu = Menu(
        menu_id=repo_id,
        name="Repository",
        path="/repository",
        component="/index/index",
        meta_title="menus.repository.title",
        meta_icon="&#xe7c3;",
        sort=16,
        keep_alive=True
    )
    db.add(repo_menu)
    
    # 资源库子菜单
    repo_children = [
        Menu(
            menu_id=generate_unique_id("menu"),
            name="RepositoryFace",
            path="face",
            component="/repository/face",
            meta_title="menus.repository.face",
            meta_icon="",
            parent_id=repo_id,
            sort=1,
            keep_alive=True
        ),
        Menu(
            menu_id=generate_unique_id("menu"),
            name="RepositoryOpen",
            path="open",
            component="/repository/open",
            meta_title="menus.repository.open",
            meta_icon="",
            parent_id=repo_id,
            sort=2,
            keep_alive=True
        )
    ]
    for menu in repo_children:
        db.add(menu)
    
    db.commit()
    logger.info("初始菜单数据创建成功")


def init() -> None:
    """
    初始化数据库数据
    """
    logger.info("开始初始化数据库数据...")
    
    db = SessionLocal()
    try:
        # 创建初始用户
        create_initial_users(db)
        
        # 创建初始角色
        create_initial_roles(db)
        
        # 创建初始组织
        create_initial_organizations(db)
        
        # 创建初始视频流
        create_initial_streams(db)
        
        # 创建初始算法
        create_initial_algorithms(db)
        
        # 创建初始模型实例
        create_initial_model_instances(db)
        
        # 创建初始系统配置
        create_initial_system_configs(db)
        
        # 创建初始菜单
        create_initial_menus(db)
        
        logger.info("数据库初始化完成")
        
    except Exception as e:
        logger.error(f"初始化数据库数据时出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init()
