#!/usr/bin/env python3
"""
通过浏览器自动化创建对话并获取对话 ID
然后直接使用该对话 ID 发送消息
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright


async def get_conversation_id_from_browser(url: str, cookies_dict: dict):
    """
    打开浏览器，让用户创建对话，然后捕获对话 ID

    Args:
        url: 雨课堂 URL
        cookies_dict: cookies 字典

    Returns:
        对话 ID
    """
    print("=" * 80)
    print("🌐 通过浏览器获取对话 ID")
    print("=" * 80)
    print("\n策略：")
    print("  由于 API 创建对话有权限限制")
    print("  我们让你在浏览器中手动创建对话")
    print("  然后捕获对话 ID 供后续使用")
    print("\n按回车开始...")
    input()

    conversation_id = None
    captured_ids = []

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)

    # 转换 cookies 格式
    cookies_for_playwright = []
    for name, value in cookies_dict.items():
        cookies_for_playwright.append({
            'name': name,
            'value': str(value),
            'domain': 'www.yuketang.cn',
            'path': '/'
        })

    context = await browser.new_context()
    await context.add_cookies(cookies_for_playwright)

    page = await context.new_page()

    # 监控网络请求
    def on_request(request):
        nonlocal captured_ids
        url = request.url

        # 捕获创建对话的请求
        if 'capability-conversation' in url and request.method == 'POST':
            print(f"\n🔵 捕获创建对话请求: {url}")
            if request.post_data:
                print(f"   数据: {request.post_data[:200]}")

    async def on_response(response):
        nonlocal conversation_id, captured_ids
        url = response.url

        # 捕获创建对话的响应
        if 'capability-conversation' in url and response.request.method == 'POST':
            try:
                data = await response.json()
                if data.get('success') and data.get('data', {}).get('id'):
                    conv_id = data['data']['id']
                    conversation_id = conv_id
                    captured_ids.append(conv_id)
                    print(f"\n✅ 捕获到对话 ID: {conv_id}")
            except:
                pass

        # 捕获发送消息的请求（也包含 conversationId）
        if 'send-message' in url:
            try:
                post_data = response.request.post_data
                if post_data:
                    post_json = json.loads(post_data)
                    if 'conversationId' in post_json:
                        conv_id = post_json['conversationId']
                        if conv_id and conv_id not in captured_ids:
                            conversation_id = conv_id
                            captured_ids.append(conv_id)
                            print(f"\n✅ 从消息请求中捕获到对话 ID: {conv_id}")
            except:
                pass

    page.on('request', on_request)
    page.on('response', on_response)

    # 访问页面
    print(f"\n🌐 访问: {url}")
    await page.goto(url, wait_until='domcontentloaded', timeout=60000)

    print("\n" + "=" * 80)
    print("👆 请在浏览器中操作")
    print("=" * 80)
    print("\n请执行以下操作之一：")
    print("  选项 1: 如果页面显示「新建对话」按钮，点击它")
    print("  选项 2: 直接在现有对话中发送一条消息（如\"你好\"）")
    print("\n我会自动捕获对话 ID...")
    print("完成后按回车继续")

    # 等待用户操作
    await asyncio.sleep(5)

    print("\n⏱️  等待你的操作...")
    print("（检测到对话 ID 后会自动显示）")

    # 持续等待用户操作
    for i in range(60):
        await asyncio.sleep(1)
        if conversation_id:
            print(f"\n✅ 已捕获对话 ID: {conversation_id}")
            break
        if i % 10 == 0:
            print(f"  等待中... ({60-i}秒剩余)", end='\r')

    if not conversation_id:
        print("\n\n⚠️  未能自动捕获对话 ID")
        print("请手动输入对话 ID（从页面 URL 或控制台查看）：")
        manual_id = input().strip()
        if manual_id:
            conversation_id = manual_id

    print("\n按回车关闭浏览器...")
    input()

    await browser.close()
    await playwright.stop()

    return conversation_id


async def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_dir = os.path.join(root_dir, "config")
    cookies_path = os.path.join(config_dir, "cookies.json")
    params_path = os.path.join(config_dir, "session_params.json")

    # 加载 cookies
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        print(f"✅ 加载了 {len(cookies)} 个 Cookie")
    except FileNotFoundError:
        print(f"❌ 未找到 {cookies_path}")
        return

    # 加载参数
    try:
        with open(params_path, 'r', encoding='utf-8') as f:
            params = json.load(f)
    except FileNotFoundError:
        params = {
            'agent_id': '916',
            'capability_id': '643248',
            'classroom_id': '28014089',
            'workflow_id': '588054'
        }

    # 构建 URL
    url = (
        f"https://www.yuketang.cn/ai-workspace/chatbot-entry-web"
        f"?aid={params.get('agent_id', '916')}"
        f"&capid={params.get('capability_id', '643248')}"
        f"&cid={params.get('classroom_id', '28014089')}"
        f"&wid={params.get('workflow_id', '588054')}"
        f"&classroom_role=5&platform=3&university_id=2968&code=coze&ent=1&report=1"
        f"&classroom_id={params.get('classroom_id', '28014089')}"
    )

    print(f"\n使用 URL: {url[:80]}...")

    # 获取对话 ID
    conversation_id = await get_conversation_id_from_browser(url, cookies)

    if conversation_id:
        print("\n" + "=" * 80)
        print("🎉 成功获取对话 ID！")
        print("=" * 80)
        print(f"\n对话 ID: {conversation_id}")

        # 保存到文件
        config = {
            'conversation_id': str(conversation_id),
            'url': url
        }

        # 确保 config 目录存在
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "conversation_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 已保存到 {config_path}")
        print("\n现在你可以:")
        print("  1. 使用这个对话 ID 直接发送消息（无需创建新对话）")
        print("  2. 运行 API 客户端时自动加载这个对话 ID")
    else:
        print("\n" + "=" * 80)
        print("❌ 未能获取对话 ID")
        print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
