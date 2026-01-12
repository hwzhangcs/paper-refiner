#!/usr/bin/env python3
"""
测试文件上传是否能在 GUI 中正确显示
"""
import json
import sys
sys.path.insert(0, '.')

from paper_api.client import YuketangAIClient


def test_upload():
    # 加载配置
    with open('config/cookies.json', 'r') as f:
        cookies = json.load(f)
    with open('config/session_params.json', 'r') as f:
        params = json.load(f)

    # 创建客户端（创建新对话以便在 GUI 中查看）
    client = YuketangAIClient(
        cookies=cookies,
        params=params,
        logger=print
    )

    # 创建新对话
    print("\n" + "=" * 60)
    print("创建新对话...")
    conv_id = client.create_new_conversation()
    if not conv_id:
        print("❌ 创建对话失败")
        return

    print(f"✅ 对话 ID: {conv_id}")
    print("=" * 60)

    # 创建一个简单的测试文件
    test_file = "/tmp/test_upload.txt"
    with open(test_file, 'w') as f:
        f.write("This is a test file for upload verification.\n")
        f.write("如果你能看到这个文件，说明上传成功！\n")

    # 发送带文件的消息
    print("\n发送带文件的消息...")
    response = client.send_message_with_file(
        message="请确认你能看到我上传的文件",
        file_path=test_file,
        stream=True
    )

    print("\n" + "=" * 60)
    print(f"请在浏览器中查看对话 ID: {conv_id}")
    print("检查文件是否显示在聊天界面中")
    print("=" * 60)


if __name__ == '__main__':
    test_upload()
