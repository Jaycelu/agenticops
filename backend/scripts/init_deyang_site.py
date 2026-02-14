"""
初始化德阳基地数据
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.automation import Site
from config.site_config import DEYANG_SITE_CONFIG


def init_deyang_site():
    """
    初始化德阳基地数据
    """
    db = SessionLocal()

    try:
        # 检查德阳基地是否已存在
        existing_site = db.query(Site).filter(
            Site.site_code == DEYANG_SITE_CONFIG["site_code"]
        ).first()

        if existing_site:
            print(f"基地 {DEYANG_SITE_CONFIG['site_name']} 已存在，跳过创建")
            return existing_site

        # 创建德阳基地
        site = Site(
            site_code=DEYANG_SITE_CONFIG["site_code"],
            site_name=DEYANG_SITE_CONFIG["site_name"],
            description=DEYANG_SITE_CONFIG["description"]
        )

        db.add(site)
        db.commit()
        db.refresh(site)

        print(f"✅ 成功创建基地: {site.site_name} (ID: {site.id})")
        return site

    except Exception as e:
        db.rollback()
        print(f"❌ 创建基地失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_deyang_site()