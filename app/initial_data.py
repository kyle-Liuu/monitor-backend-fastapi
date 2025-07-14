import asyncio
import logging
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory, init_db
from app.db.models import User, Menu
from app.core.security import get_password_hash
from app.utils.utils import generate_unique_id

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_initial_users(db: AsyncSession) -> None:
    """
    创建初始用户
    """
    # 检查是否已存在管理员
    result = await db.execute(select(User).where(User.username == "super"))
    if result.scalars().first():
        logger.info("超级管理员用户已存在，跳过创建")
        return
    
    # 创建超级管理员
    super_admin = User(
        user_id=generate_unique_id("user"),
        username="super",
        email="super@example.com",
        hashed_password=get_password_hash("123456"),
        fullname="超级管理员",
        is_active=True,
        is_superuser=True,
        is_admin=False,
        role="R_SUPER",
        avatar="/public/assets/avatar/default.webp"
    )
    db.add(super_admin)
    
    # 创建管理员
    admin_user = User(
        user_id=generate_unique_id("user"),
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("123456"),
        fullname="管理员",
        is_active=True,
        is_superuser=False,
        is_admin=True,
        role="R_ADMIN",
        avatar="/public/assets/avatar/default.webp"
    )
    db.add(admin_user)
    
    # 创建普通用户
    normal_user = User(
        user_id=generate_unique_id("user"),
        username="user",
        email="user@example.com",
        hashed_password=get_password_hash("123456"),
        fullname="普通用户",
        is_active=True,
        is_superuser=False,
        is_admin=False,
        role="R_USER",
        avatar="/public/assets/avatar/default.webp"
    )
    db.add(normal_user)
    
    await db.commit()
    logger.info("初始用户创建成功")


async def create_initial_menus(db: AsyncSession) -> None:
    """
    创建初始菜单
    
    注意：此处菜单数据与前端路由配置(monitor/src/router/routes/asyncRoutes.ts)保持同步
    如果前端路由配置有更新，此处也需要相应更新，但不修改前端文件
    """
    # 检查是否已存在菜单
    result = await db.execute(select(Menu).where(Menu.name == "Dashboard"))
    if result.scalars().first():
        logger.info("菜单数据已存在，跳过创建")
        return

    # 基于前端 asyncRoutes.ts 创建菜单数据
    dashboard_id = generate_unique_id("menu")
    
    # 创建Dashboard主菜单
    dashboard = Menu(
        menu_id=dashboard_id,
        name="Dashboard",
        path="/dashboard",
        component="/index/index",
        meta_title="menus.dashboard.title",
        meta_icon="&#xe721;",
        sort=1,
        keep_alive=True
    )
    db.add(dashboard)
    await db.flush()
    
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
    
    # 监控菜单
    monitor_menu = Menu(
        menu_id=generate_unique_id("menu"),
        name="Monitor",
        path="/monitor",
        component="/monitor",
        meta_title="menus.monitor.title",
        meta_icon="&#xe8ba;",
        sort=2,
        keep_alive=True
    )
    db.add(monitor_menu)
    
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
            keep_alive=True
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
    
    await db.commit()
    logger.info("初始菜单创建成功")


async def init() -> None:
    """
    初始化数据
    """
    logger.info("创建初始数据")
    
    # 初始化数据库
    await init_db()
    
    async with async_session_factory() as db:
        await create_initial_users(db)
        await create_initial_menus(db)
    
    logger.info("初始数据创建完成")


if __name__ == "__main__":
    asyncio.run(init())
