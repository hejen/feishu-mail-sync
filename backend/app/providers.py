from typing import Dict
from app.models.schemas import ProviderConfig


# 支持的邮箱提供商配置
EMAIL_PROVIDERS: Dict[str, ProviderConfig] = {
    "qq": ProviderConfig(
        name="QQ邮箱",
        value="qq",
        imap_server="imap.qq.com",
        imap_port=993,
        help_url="https://service.mail.qq.com/detail/0/75"
    ),
    "163": ProviderConfig(
        name="网易163邮箱",
        value="163",
        imap_server="imap.163.com",
        imap_port=993,
        help_url="https://help.mail.163.com/faqDetail.do?code=d7a5dc8471cd0b5b97e2c3cfff5f8f37"
    ),
    "126": ProviderConfig(
        name="网易126邮箱",
        value="126",
        imap_server="imap.126.com",
        imap_port=993,
        help_url="https://help.mail.126.com/faqDetail.do?code=d7a5dc8471cd0b5b97e2c3cfff5f8f37"
    ),
    "feishu": ProviderConfig(
        name="飞书邮箱",
        value="feishu",
        imap_server="imap.feishu.cn",
        imap_port=993,
        help_url="https://www.feishu.cn/hc/zh-CN/articles/360049067533"
    )
}


def get_provider_config(provider: str) -> ProviderConfig:
    """获取邮箱提供商配置"""
    if provider not in EMAIL_PROVIDERS:
        raise ValueError(f"不支持的邮箱提供商: {provider}")
    return EMAIL_PROVIDERS[provider]


def get_all_providers() -> list:
    """获取所有支持的邮箱提供商"""
    return list(EMAIL_PROVIDERS.values())
