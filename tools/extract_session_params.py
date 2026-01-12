#!/usr/bin/env python3
"""
提取雨课堂会话参数
自动从你的浏览器会话中提取正确的 agent_id, capability_id 等参数
"""
import asyncio
import json
import os
import re
import sys
import time
from playwright.async_api import async_playwright


def safe_input(prompt: str = "") -> str:
    """在非交互环境下避免 EOFError."""
    try:
        return input(prompt)
    except EOFError:
        return ""


async def extract_session_params(url: str = None, wait_time: int = 60, config_name: str = None):
    """
    打开浏览器，监控网络请求，提取正确的参数

    Args:
        url: 雨课堂 URL，如果不提供则请求用户输入
        wait_time: 等待时间
        config_name: 配置名称后缀 (例如 'review' -> session_params_review.json)

    Returns:
        包含所有参数的字典
    """
    if not url:
        print("\n请输入你的雨课堂 AI 对话 URL：")
        print("（从浏览器地址栏复制，包含 ?aid=xxx&capid=xxx... 等参数）")
        print("\n示例:")
        print("https://www.yuketang.cn/ai-workspace/chatbot-entry-web?aid=916&capid=643248&...")
        print("\n你的 URL：")
        url = safe_input().strip()

        if not url or not url.startswith('http'):
            print("\n⚠️  URL 无效，使用默认 URL")
            url = "https://www.yuketang.cn/ai-workspace/chatbot-entry-web"
    print("=" * 80)
    print("🔍 雨课堂会话参数提取工具")
    if config_name:
        print(f"📁 配置名称: {config_name}")
    print("=" * 80)

    # 从 URL 中提取初始参数
    initial_params = {}
    try:
        if 'aid=' in url:
            match = re.search(r'aid=(\d+)', url)
            if match:
                initial_params['agent_id'] = match.group(1)
        if 'capid=' in url:
            match = re.search(r'capid=(\d+)', url)
            if match:
                initial_params['capability_id'] = match.group(1)
        if 'cid=' in url:
            match = re.search(r'cid=(\d+)', url)
            if match:
                initial_params['classroom_id'] = match.group(1)
        elif 'classroom_id=' in url:
            match = re.search(r'classroom_id=(\d+)', url)
            if match:
                initial_params['classroom_id'] = match.group(1)
        if 'wid=' in url:
            match = re.search(r'wid=(\d+)', url)
            if match:
                initial_params['workflow_id'] = match.group(1)
    except Exception as e:
        print(f"⚠️  URL 解析警告: {e}")

    captured_data = {
        'params': initial_params,
        'cookies': {},
        'headers': {},
        'api_calls': []
    }

    print("\n🚀 正在启动浏览器...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 监听网络请求
        async def on_request(request):
            # 捕获发送消息的请求
            if 'send-message' in request.url and request.method == 'POST':
                try:
                    post_data = request.post_data
                    if post_data:
                        post_json = json.loads(post_data)
                        captured_data['api_calls'].append({
                            'url': request.url,
                            'data': post_json
                        })
                        print("\n✅ 捕获到 API 请求！")
                        
                        # 提取更准确的参数
                        if 'messageInfo' in post_json:
                            info = post_json['messageInfo']
                            if 'agentId' in info:
                                captured_data['params']['agent_id'] = str(info['agentId'])
                                print(f"  ✓ agent_id: {info['agentId']}")
                            if 'workflow_id' in info:
                                captured_data['params']['workflow_id'] = str(info['workflow_id'])
                                print(f"  ✓ workflow_id: {info['workflow_id']}")
                            if 'classroom_id' in info:
                                captured_data['params']['classroom_id'] = str(info['classroom_id'])
                                print(f"  ✓ classroom_id: {info['classroom_id']}")
                        
                        if 'conversationId' in post_json:
                            captured_data['params']['conversation_id'] = str(post_json['conversationId'])
                            print(f"  ✓ conversation_id: {post_json['conversationId']}")
                        
                        # 尝试提取 workflow_id 如果之前没提取到
                        if 'workflow_id' not in captured_data['params']:
                            if 'workflow_id' in post_json:
                                captured_data['params']['workflow_id'] = str(post_json['workflow_id'])
                                print(f"  ✓ workflow_id (from POST): {post_json['workflow_id']}")

                except:
                    pass

            # 保存重要的 headers
            for key in ['cookie', 'x-csrftoken', 'authorization', 'referer']:
                if key in request.headers:
                    captured_data['headers'][key] = request.headers[key]

        page.on('request', on_request)

        # 访问雨课堂
        print(f"\n🌐 访问: {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)

        # 等待用户操作
        print(f"\n⏱️  等待 {wait_time} 秒...")
        print("请：")
        print("  1. 登录")
        print("  2. 进入对话界面")
        print("  3. 发送至少 1 条消息")
        print()

        for i in range(wait_time):
            remaining = wait_time - i
            print(f"  剩余 {remaining} 秒...", end='\r')
            await asyncio.sleep(1)

        print("\n\n📋 提取 Cookies...")
        cookies = await context.cookies()
        captured_data['cookies'] = {c['name']: c['value'] for c in cookies}

        print(f"✅ 提取了 {len(captured_data['cookies'])} 个 Cookie")

        # 保存所有数据
        print("\n💾 保存数据...")

        # 确保 config 目录存在
        os.makedirs('config', exist_ok=True)

        # 确定文件名
        if config_name:
            params_file = f"config/session_params_{config_name}.json"
            conv_file = f"config/conversation_config_{config_name}.json"
        else:
            params_file = "config/session_params.json"
            conv_file = "config/conversation_config.json"
        
        # cookies 始终保存为 default，除非想分离（这里保持共享）
        cookies_file = "config/cookies.json"

        # 保存 cookies（如果存在则先备份）
        if os.path.exists(cookies_file):
            backup_name = f"{cookies_file}.bak.{int(time.time())}"
            try:
                os.replace(cookies_file, backup_name)
                print(f"  ✓ 备份 {cookies_file} -> {backup_name}")
            except OSError:
                pass
        
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(captured_data['cookies'], f, indent=2, ensure_ascii=False)
        print(f"  ✓ {cookies_file}")

        conversation_id = captured_data['params'].pop('conversation_id', None)
        if conversation_id:
            conversation_config = {
                'conversation_id': str(conversation_id),
                'url': url
            }
            with open(conv_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_config, f, indent=2, ensure_ascii=False)
            print(f"  ✓ {conv_file}")

        # 保存参数
        with open(params_file, 'w', encoding='utf-8') as f:
            json.dump(captured_data['params'], f, indent=2, ensure_ascii=False)
        print(f"  ✓ {params_file}")

        # 保存完整报告 (可选)
        # with open('config/session_report.json', 'w', encoding='utf-8') as f: ...

        print("\n" + "=" * 80)
        print("✅ 参数提取完成！")
        print("=" * 80)

        if captured_data['params']:
            print("\n📊 提取到的参数：")
            for key, value in captured_data['params'].items():
                print(f"  {key}: {value}")
        else:
            print("\n⚠️  未能提取到参数")
            print("请确保你：")
            print("  1. 已经登录")
            print("  2. 进入了对话界面")
            print("  3. 发送了至少 1 条消息")

        print("\n按回车关闭浏览器...")
        safe_input()

        await browser.close()
        # await p.stop() - handled by context manager

        return captured_data


async def main():
    print("=" * 80)
    print("🚀 雨课堂参数和 Cookies 提取")
    print("=" * 80)

    url = None
    config_name = None

    # 简单的参数解析
    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 2:
        config_name = sys.argv[2]

    await extract_session_params(url=url, wait_time=60, config_name=config_name)


if __name__ == '__main__':
    asyncio.run(main())
