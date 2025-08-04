"""
数据库模型定义模块
定义所有数据库表的模型类
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, func, Float
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    avatar = Column(String, nullable=True)  # 用户头像URL
    is_active = Column(Boolean, default=True)
    role = Column(String, default="R_USER")  # 支持多角色：R_SUPER,R_ADMIN,R_USER
    mobile = Column(String, nullable=True)  # 手机号
    tags = Column(String, nullable=True)    # 标签列表，逗号分隔
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    @property
    def is_superuser(self):
        """是否超级管理员的计算属性"""
        user_roles = self.role.split(",") if self.role else []
        return "R_SUPER" in user_roles
    
    @property
    def fullname(self):
        """兼容性方法，返回full_name"""
        return self.full_name
    
    def has_role(self, required_role: str) -> bool:
        """检查用户是否拥有指定角色"""
        user_roles = self.role.split(",") if self.role else []
        return required_role in user_roles
    
    def has_any_role(self, required_roles: list) -> bool:
        """检查用户是否拥有任意一个指定角色"""
        user_roles = self.role.split(",") if self.role else []
        return any(role in user_roles for role in required_roles)


class Role(Base):
    """角色模型"""
    __tablename__ = "roles"
    
    role_id = Column(String, primary_key=True, index=True)  # role7a2b1c3d
    role_code = Column(String, unique=True, nullable=False)  # R_SUPER, R_ADMIN, R_USER
    role_name = Column(String, nullable=False)  # 超级管理员, 管理员, 普通用户
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Organization(Base):
    """组织模型 - 视频流安装区域"""
    __tablename__ = "organizations"
    
    org_id = Column(String, primary_key=True, index=True)  # org7a2b1c3d
    name = Column(String, nullable=False)  # 区域名称
    parent_id = Column(String, ForeignKey("organizations.org_id"), nullable=True)
    path = Column(String)  # 层级路径：/1/2/3/
    description = Column(Text, nullable=True)
    status = Column(String, default="active")  # active, inactive
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 自引用关系
    children = relationship("Organization", backref="parent", remote_side=[org_id])


class OrganizationBinding(Base):
    """组织绑定模型 - 组织与视频流的绑定关系"""
    __tablename__ = "organization_bindings"
    
    binding_id = Column(String, primary_key=True, index=True)  # bind7a2b1c3d
    org_id = Column(String, ForeignKey("organizations.org_id"))
    stream_id = Column(String, ForeignKey("streams.stream_id"))
    created_at = Column(DateTime, default=func.now())
    
    # 关联关系
    organization = relationship("Organization")
    stream = relationship("VideoStream", back_populates="bindings")


class BlacklistedToken(Base):
    """已失效令牌黑名单"""
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now())


class Menu(Base):
    """菜单模型"""
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    component = Column(String, nullable=True)
    redirect = Column(String, nullable=True)
    meta_title = Column(String, nullable=False)
    meta_icon = Column(String, nullable=True)
    parent_id = Column(String, ForeignKey("menus.menu_id"), nullable=True)
    sort = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    roles = Column(String, nullable=True)  # 使用新角色编码：R_SUPER,R_ADMIN
    keep_alive = Column(Boolean, default=True)
    auth_list = Column(Text, nullable=True)
    show_badge = Column(Boolean, default=False)
    show_text_badge = Column(String, nullable=True)
    is_hide_tab = Column(Boolean, default=False)
    is_full_page = Column(Boolean, default=False)
    fixed_tab = Column(Boolean, default=False)
    active_path = Column(String, nullable=True)
    link = Column(String, nullable=True)
    is_iframe = Column(Boolean, default=False)
    is_first_level = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 自引用关系
    children = relationship("Menu", 
                           backref="parent",
                           remote_side=[menu_id],
                           cascade="all, delete")


class VideoStream(Base):
    """视频流模型 - 支持流复用"""
    __tablename__ = "streams"

    stream_id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    url = Column(String)
    stream_type = Column(String, default="rtsp")  # rtsp, rtmp, http
    protocol = Column(String, default="rtsp")     # rtsp, GB28181, rtmp, hls
    status = Column(String, default="inactive")   # active, inactive, error
    is_forwarding = Column(Boolean, default=False)  # 是否已转发（必须转发后才能执行任务）
    frame_width = Column(Integer, nullable=True)  # 帧宽度
    frame_height = Column(Integer, nullable=True)  # 帧高度
    fps = Column(Float, nullable=True)  # 帧率
    consumer_count = Column(Integer, default=0)  # 消费者数量（用于流复用）
    last_frame_time = Column(DateTime, nullable=True)  # 最后一帧时间
    last_online_time = Column(DateTime, nullable=True)  # 最后在线时间
    frame_count = Column(Integer, default=0)  # 处理帧数
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    tasks = relationship("Task", back_populates="stream")
    bindings = relationship("OrganizationBinding", back_populates="stream")


class Algorithm(Base):
    """算法模型 - 支持模型实例共享"""
    __tablename__ = "algorithms"

    algo_id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    package_name = Column(String)
    algorithm_type = Column(String, default="detection")  # detection, tracking, recognition
    version = Column(String, default="1.0.0")
    config = Column(Text, nullable=True)  # JSON配置
    status = Column(String, default="inactive")  # active, inactive, error
    path = Column(String, nullable=True)  # 算法包路径
    model_path = Column(String, nullable=True)  # 模型文件路径
    max_instances = Column(Integer, default=3)  # 最大实例数
    current_instances = Column(Integer, default=0)  # 当前实例数
    device_type = Column(String, default="cpu,gpu")  # 支持的设备类型：cpu,gpu,cuda等
    memory_usage = Column(Float, nullable=True)  # 内存使用量(MB)
    inference_time = Column(Float, nullable=True)  # 平均推理时间(ms)
    error_message = Column(Text, nullable=True)  # 错误信息
    author = Column(String, nullable=True)  # 作者信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    tasks = relationship("Task", back_populates="algorithm")
    model_instances = relationship("ModelInstance", back_populates="algorithm")


class Task(Base):
    """任务模型 - 支持多对多关系"""
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    stream_id = Column(String, ForeignKey("streams.stream_id"))
    algorithm_id = Column(String, ForeignKey("algorithms.algo_id"))
    status = Column(String, default="created")  # created, running, stopped, error
    config = Column(Text, nullable=True)  # JSON配置
    alarm_config = Column(Text, nullable=True)  # JSON告警配置
    zone_config = Column(Text, nullable=True)  # JSON区域配置
    frame_count = Column(Integer, default=0)  # 处理帧数
    last_frame_time = Column(DateTime, nullable=True)  # 最后一帧时间
    processing_time = Column(Float, default=0.0)  # 总处理时间(秒)
    detection_count = Column(Integer, default=0)  # 检测次数
    alarm_count = Column(Integer, default=0)  # 告警次数
    error_message = Column(Text, nullable=True)  # 错误信息
    model_instance_id = Column(String, nullable=True)  # 使用的模型实例ID
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    stream = relationship("VideoStream", back_populates="tasks")
    algorithm = relationship("Algorithm", back_populates="tasks")
    alarms = relationship("Alarm", back_populates="task")


class Alarm(Base):
    """告警模型"""
    __tablename__ = "alarms"

    alarm_id = Column(String, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("tasks.task_id"))
    alarm_type = Column(String)  # person, vehicle, etc.
    confidence = Column(Float)
    bbox = Column(Text, nullable=True)  # JSON格式的边界框 [x, y, w, h]
    original_image = Column(String, nullable=True)  # 原始图片路径
    processed_image = Column(String, nullable=True)  # 处理后图片路径
    video_clip = Column(String, nullable=True)  # 视频片段路径
    # 告警状态和等级
    status = Column(String, default="new")        # new, processed, ignored
    level = Column(String, default="medium")      # low, medium, high, critical
    # 处理信息
    processed_by = Column(String, ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    process_comment = Column(Text, nullable=True)
    # 兼容性字段（保留但使用新字段）
    processed = Column(Boolean, default=False)  # 兼容性字段
    severity = Column(String, default="medium") # 兼容性字段
    created_at = Column(DateTime, default=func.now())
    
    # 关联
    task = relationship("Task", back_populates="alarms") 
    processor = relationship("User", foreign_keys=[processed_by])


class ModelInstance(Base):
    """模型实例模型 - 支持实例池管理"""
    __tablename__ = "model_instances"

    instance_id = Column(String, primary_key=True, index=True)
    algorithm_id = Column(String, ForeignKey("algorithms.algo_id"))
    instance_name = Column(String, nullable=False)  # 实例名称
    status = Column(String, default="idle")  # idle, busy, error
    device_type = Column(String, default="cpu")  # cpu, gpu
    memory_usage = Column(Float, nullable=True)  # 内存使用量(MB)
    load_time = Column(DateTime, nullable=True)  # 加载时间
    last_used = Column(DateTime, nullable=True)  # 最后使用时间
    use_count = Column(Integer, default=0)  # 使用次数
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    algorithm = relationship("Algorithm", back_populates="model_instances")


class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_configs"

    config_id = Column(String, primary_key=True, index=True)
    config_key = Column(String, unique=True, index=True, nullable=False)
    config_value = Column(Text, nullable=True)
    config_type = Column(String, default="string")  # string, int, float, bool, json
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=True)  # 是否系统配置
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now()) 