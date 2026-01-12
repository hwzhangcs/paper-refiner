"""Configuration loaders for the SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs


def _load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_cookies(path: str = "config/cookies.json") -> Dict[str, str]:
    return _load_json(path)


def load_session_params(path: str = "config/session_params.json") -> Dict[str, Any]:
    return _load_json(path)


def load_conversation_config(path: str = "config/conversation_config.json") -> Dict[str, Any]:
    return _load_json(path)


def load_conversation_id(path: str = "config/conversation_config.json") -> Optional[int]:
    try:
        config = load_conversation_config(path)
    except FileNotFoundError:
        return None

    conv_id = config.get("conversation_id")
    if conv_id is None:
        return None
    try:
        return int(conv_id)
    except (TypeError, ValueError):
        return None


def extract_params_from_url(url: str) -> Dict[str, Any]:
    """
    从雨课堂 AI 工作区 URL 提取 session 参数

    Args:
        url: 雨课堂 AI 工作区 URL
            例如: https://www.yuketang.cn/ai-workspace/chatbot-entry-web?aid=916&capid=683555&...

    Returns:
        包含 session 参数的字典 (agent_id, capability_id, classroom_id, workflow_id, entity_type)

    Raises:
        ValueError: 如果 URL 格式无效或缺少必需参数
    """
    try:
        parsed = urlparse(url)

        # 验证域名
        if 'yuketang.cn' not in parsed.netloc:
            raise ValueError(f"URL 域名无效: {parsed.netloc}，应为 yuketang.cn")

        # 解析查询参数
        params = parse_qs(parsed.query)

        # 验证必需参数
        required_params = ['aid', 'capid', 'cid', 'wid']
        missing_params = [p for p in required_params if p not in params]

        if missing_params:
            raise ValueError(f"URL 缺少必需参数: {', '.join(missing_params)}")

        # 提取参数（parse_qs 返回列表，取第一个值）
        session_params = {
            'agent_id': params['aid'][0],
            'capability_id': params['capid'][0],
            'classroom_id': params['cid'][0],
            'workflow_id': params['wid'][0],
            'entity_type': int(params.get('ent', ['1'])[0])
        }

        return session_params

    except Exception as e:
        raise ValueError(f"解析 URL 失败: {str(e)}")


def build_client_from_url(url: str, cookies: Dict[str, str], logger=None):
    """
    从雨课堂 AI 工作区 URL 直接创建客户端

    这是创建新工作区客户端的最快方式，无需预先创建配置文件。

    Args:
        url: 雨课堂 AI 工作区 URL
            例如: https://www.yuketang.cn/ai-workspace/chatbot-entry-web?aid=916&capid=683555&...
        cookies: 认证 cookies 字典
        logger: 可选的日志函数（如 print）

    Returns:
        配置好的 YuketangAIClient 实例

    Raises:
        ValueError: 如果 URL 格式无效

    Example:
        >>> from paper_api import build_client_from_url
        >>> from paper_api.config import load_cookies
        >>> cookies = load_cookies()
        >>> url = "https://www.yuketang.cn/ai-workspace/chatbot-entry-web?aid=916&capid=683555&..."
        >>> client = build_client_from_url(url, cookies, logger=print)
        >>> response = client.send_message("你好")
    """
    from .client import YuketangAIClient

    params = extract_params_from_url(url)

    return YuketangAIClient(
        cookies,
        params=params,
        conversation_id=None,
        logger=logger,
    )


def build_client_from_files(
    config_name: str = 'default',
    *,
    cookies_path: Optional[str] = None,
    logger=None,
):
    """
    从配置文件创建客户端，支持多个工作区配置

    Args:
        config_name: 配置名称
            - 'default': 使用 session_params.json（向后兼容）
            - 其他名称: 使用 session_params_<name>.json
        cookies_path: cookies 文件路径（可选，默认为 config/cookies.json）
        logger: 可选的日志函数（如 print）

    Returns:
        配置好的 YuketangAIClient 实例

    Example:
        >>> from paper_api import build_client_from_files
        >>> # 使用默认配置
        >>> client1 = build_client_from_files('default', logger=print)
        >>> # 使用 workspace2 配置
        >>> client2 = build_client_from_files('workspace2', logger=print)
    """
    from .client import YuketangAIClient

    # 确定文件路径
    if cookies_path is None:
        cookies_path = "config/cookies.json"

    if config_name == 'default':
        params_path = "config/session_params.json"
        conversation_path = "config/conversation_config.json"
    else:
        params_path = f"config/session_params_{config_name}.json"
        conversation_path = f"config/conversation_config_{config_name}.json"

    # 加载配置
    cookies = load_cookies(cookies_path)
    try:
        params = load_session_params(params_path)
    except FileNotFoundError:
        params = {}

    try:
        conversation_id = load_conversation_id(conversation_path)
    except FileNotFoundError:
        conversation_id = None

    return YuketangAIClient(
        cookies,
        params=params,
        conversation_id=conversation_id,
        logger=logger,
    )
