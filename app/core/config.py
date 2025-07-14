import secrets
from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_STR: str = "/api"
    API_VERSION: str = "1.0.0"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60分钟 * 24小时 * 8天 = 8天
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    # 刷新令牌过期时间：60分钟 * 24小时 * 30天 = 30天
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30
    # BACKEND_CORS_ORIGINS是用于设置跨域的域名列表
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    PROJECT_NAME: str = "AI智能监控系统"
    
    # SQLite数据库配置
    SQLITE_URL: str = "sqlite+aiosqlite:///./app.db"
    
    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings() 