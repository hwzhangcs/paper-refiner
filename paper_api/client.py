#!/usr/bin/env python3
"""
雨课堂 AI 直接 API 客户端
基于逆向分析结果，直接调用 API，无需浏览器
"""

from __future__ import annotations

import json
import requests
from typing import Callable, Dict, List, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

Logger = Optional[Callable[[str], None]]


class YuketangAIClient:
    """雨课堂 AI API 客户端"""

    def __init__(
        self,
        cookies: Dict[str, str],
        params: Optional[Dict[str, str]] = None,
        conversation_id: Optional[int] = None,
        logger: Logger = None,
    ):
        """
        初始化客户端

        Args:
            cookies: 从浏览器中提取的 cookies（需要登录后获取）
            params: 会话参数（agent_id, capability_id 等）
            conversation_id: 当前对话 ID（可选）
            logger: 可选的日志函数（如 print）
        """
        self.base_url = "https://www.yuketang.cn"
        self.cookies = cookies
        self._logger = logger
        self._stream_buffer: Optional[List[str]] = None

        # 初始化 Session 以复用连接
        self.session = requests.Session()

        params = params or {}

        # 从参数中提取，或使用默认值
        self.agent_id = params.get("agent_id", "916")
        self.capability_id = params.get("capability_id", "643248")
        self.classroom_id = params.get("classroom_id", "28014089")
        self.workflow_id = params.get("workflow_id", "588054")
        self.entity_type = params.get("entity_type", 1)

        self._log("📋 使用参数:")
        self._log(f"   agent_id: {self.agent_id}")
        self._log(f"   capability_id: {self.capability_id}")
        self._log(f"   classroom_id: {self.classroom_id}")
        self._log(f"   workflow_id: {self.workflow_id}")

        self.conversation_id = conversation_id
        if self.conversation_id:
            self._log(f"\n✅ 使用对话 ID: {self.conversation_id}")

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.base_url}/ai-workspace/chatbot-entry-web",
            "xt-agent": "web",
            "xtbz": "ykt",
        }

        # 添加必要的 headers
        if "csrftoken" in cookies:
            self.headers["X-CSRFToken"] = cookies["csrftoken"]
        if "university_id" in cookies:
            self.headers["university-id"] = cookies["university_id"]
            self.headers["uv-id"] = cookies["university_id"]

        # 更新 session headers 和 cookies
        self.session.headers.update(self.headers)
        self.session.cookies.update(self.cookies)

    def _log(self, message: str) -> None:
        if self._logger:
            self._logger(message)

    def _stream(self, message: str) -> None:
        if not self._logger:
            return
        if self._logger is print:
            print(message, end="", flush=True)
            return
        if self._stream_buffer is not None:
            self._stream_buffer.append(message)
            return
        self._logger(message)

    def _start_stream_buffer(self) -> None:
        if not self._logger or self._logger is print:
            self._stream_buffer = None
            return
        self._stream_buffer = []

    def _flush_stream_buffer(self) -> None:
        if not self._stream_buffer:
            self._stream_buffer = None
            return
        message = "".join(self._stream_buffer)
        self._stream_buffer = None
        self._logger(message)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def create_new_conversation(self) -> Optional[int]:
        """
        创建新对话

        Returns:
            对话 ID，如果失败返回 None
        """
        url = f"{self.base_url}/c27/online_courseware/capability-conversation/"

        data = {
            "capability_id": int(self.capability_id),
            "entity_id": self.classroom_id,
            "entity_type": self.entity_type,
            "type": 1,
            "classroom_id": self.classroom_id,
            "workflow_id": self.workflow_id,
        }

        try:
            response = self.session.post(url, json=data, timeout=300)

            result = response.json()
            if result.get("data", {}).get("id"):
                self.conversation_id = result["data"]["id"]
                self._log(f"✅ 创建新对话成功: {self.conversation_id}")
                return self.conversation_id

            self._log(f"❌ 创建对话失败: {result}")
            return None

        except Exception as e:
            self._log(f"❌ 创建对话出错: {e}")
            raise  # Let retry handle it if it's network related, or caller handle logic errors

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def send_message(
        self,
        message: str,
        stream: bool = True,
        allow_create_conversation: bool = True,
    ) -> Optional[str]:
        """
        发送消息到 AI

        Args:
            message: 要发送的消息
            stream: 是否使用流式响应
            allow_create_conversation: 如果没有对话 ID，是否尝试创建新对话

        Returns:
            AI 的回复内容
        """
        if not self.conversation_id:
            if not allow_create_conversation:
                self._log("⚠️  没有对话 ID，无法在 OpenAI 格式下创建新对话")
                self._log("   请先运行: uv run python tools/get_conversation_id.py")
                return None
            self._log("⚠️  没有对话 ID，尝试创建新对话...")
            try:
                conv_id = self.create_new_conversation()
                if not conv_id:
                    self._log(
                        "❌ 创建对话失败！请运行: uv run python tools/get_conversation_id.py"
                    )
                    return None
            except Exception:
                return None

        url = f"{self.base_url}/api/v3/ai/online-courseware/capability-conversation/send-message-stream"

        # 使用真实捕获的请求格式
        data = {
            "messageInfo": {
                "templateId": 0,
                "source": 0,
                "content": message,
                "agentId": self.agent_id,
                "type": "talk",
                "searchId": "",
                "files": [],
                "source_id": 0,
                "attachments": [],
                "text": message,
                "id": 0,
                "multi": False,
                "quote_id": "",
                "quote_content": "",
                "_data": {},
                "workflow_id": self.workflow_id,
                "classroom_id": self.classroom_id,
            },
            "conversationId": int(self.conversation_id),
        }

        try:
            if stream:
                self._start_stream_buffer()
                response = self.session.post(url, json=data, stream=True, timeout=120)

                full_response = ""
                self._stream("🤖 AI: ")

                first_line = True
                for line in response.iter_lines():
                    if line:
                        try:
                            line_text = line.decode("utf-8")

                            # 解析每行 JSON（不是 SSE 格式，直接是 JSON）
                            chunk = json.loads(line_text)

                            # 第一行是 ID 信息，跳过
                            if first_line and "reply_id" in chunk:
                                first_line = False
                                continue

                            # 提取 content 字段
                            if "content" in chunk:
                                text = chunk["content"]
                                if text:
                                    self._stream(text)
                                    full_response += text

                        except json.JSONDecodeError:
                            self._log(
                                f"⚠️ Warning: Failed to parse JSON chunk: {line[:50]}..."
                            )
                            continue
                        except Exception as e:
                            self._log(f"❌ Error processing chunk: {e}")
                            continue

                if self._logger is print:
                    print()
                else:
                    self._flush_stream_buffer()
                return full_response

            response = self.session.post(url, json=data, timeout=30)

            try:
                result = response.json()
                return result.get("data", {}).get("content", str(result))
            except json.JSONDecodeError:
                # Some endpoints return line-delimited JSON even when stream=False.
                full_response = ""
                for line in response.text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(chunk, dict) and "content" in chunk:
                        text = chunk.get("content")
                        if text:
                            full_response += text
                if full_response:
                    return full_response
                return response.text or None

        except Exception as e:
            self._log(f"❌ 发送消息出错: {e}")
            raise  # Re-raise for tenacity to handle retry if applicable

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_conversation_history(
        self, conversation_id: Optional[int] = None, page_size: int = 40
    ) -> List[Dict]:
        """获取对话历史"""
        conv_id = conversation_id or self.conversation_id
        if not conv_id:
            self._log("⚠️  没有对话 ID")
            return []

        url = f"{self.base_url}/c27/online_courseware/capability-conversation/{conv_id}/talk_records/"

        params = {
            "page_size": page_size,
            "workflow_id": self.workflow_id,
            "classroom_id": self.classroom_id,
            "agent_id": self.agent_id,
        }

        try:
            response = self.session.get(url, params=params, timeout=20)

            result = response.json()
            records = result.get("data", {}).get("results", [])

            messages = []
            for record in records:
                if record.get("content"):
                    messages.append({"role": "user", "content": record["content"]})

                if record.get("answer"):
                    messages.append({"role": "assistant", "content": record["answer"]})

            return messages

        except Exception as e:
            self._log(f"❌ 获取历史记录出错: {e}")
            return []

    def list_conversations(self) -> List[Dict]:
        """列出所有对话"""
        url = f"{self.base_url}/c27/online_courseware/capability-conversation/"

        params = {
            "capability_id": self.capability_id,
            "entity_id": self.classroom_id,
            "entity_type": self.entity_type,
            "workflow_id": self.workflow_id,
            "classroom_id": self.classroom_id,
        }

        try:
            response = self.session.get(url, params=params, timeout=20)

            result = response.json()
            conversations = result.get("data", {}).get("results", [])
            return conversations

        except Exception as e:
            self._log(f"❌ 获取对话列表出错: {e}")
            return []

    def chat_openai_format(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """OpenAI 格式对话"""
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        if not user_messages:
            return ""

        last_message = user_messages[-1]["content"]
        try:
            return self.send_message(last_message, allow_create_conversation=False)
        except Exception:
            return None

    def get_oss_upload_token(self) -> Optional[Dict]:
        """获取 OSS 上传凭证"""
        try:
            uv_id = (
                self.cookies.get("uv_id") or self.cookies.get("university_id") or "0"
            )
            url = (
                f"{self.base_url}/pc/oss_sts_token/ai_conversation/"
                f"?agent_id={self.agent_id}&conversation_id=ai_conversation&uv_id={uv_id}"
            )
            response = self.session.get(url, timeout=20)

            result = response.json()
            data = result.get("data", {})
            creds = data.get("credentials", {})
            if not creds:
                self._log(f"❌ 获取 OSS 凭证失败: {result}")
                return None

            token = {
                "accessKeyId": creds.get("AccessKeyId") or creds.get("accessKeyId"),
                "accessKeySecret": creds.get("AccessKeySecret")
                or creds.get("accessKeySecret"),
                "securityToken": creds.get("SecurityToken")
                or creds.get("securityToken"),
                "bucket": creds.get("BucketName") or creds.get("bucket"),
                "region": creds.get("Region")
                or creds.get("region")
                or "oss-cn-beijing",
                "uploadDir": creds.get("UploadDir") or creds.get("uploadDir"),
                "expiration": creds.get("Expiration") or creds.get("expiration"),
            }
            if (
                not token["accessKeyId"]
                or not token["accessKeySecret"]
                or not token["securityToken"]
            ):
                self._log(f"❌ OSS 凭证字段不完整: {result}")
                return None

            self._log("✅ 获取 OSS 凭证成功")
            return token

        except Exception as e:
            self._log(f"❌ 获取 OSS 凭证出错: {e}")
            return None

    def upload_file(self, file_path: str) -> Optional[Dict]:
        """上传文件到 OSS"""
        import os
        import hashlib
        import base64
        from datetime import datetime
        import uuid

        if not os.path.exists(file_path):
            self._log(f"❌ 文件不存在: {file_path}")
            return None

        oss_token = self.get_oss_upload_token()
        if not oss_token:
            return None

        with open(file_path, "rb") as f:
            file_content = f.read()

        file_name = os.path.basename(file_path)
        file_size = len(file_content)
        file_ext = os.path.splitext(file_name)[1]

        # 计算文件 MD5
        file_md5 = hashlib.md5(file_content).hexdigest()

        timestamp = str(int(datetime.now().timestamp() * 1000))
        file_uuid = str(uuid.uuid4())
        oss_path = f"rain_ai_knowledge_base/user_chat_file/-1/{self.agent_id}/ai_conversation/{timestamp}{file_uuid}{file_ext}"

        bucket = "ai-course-base-resource"
        region = "oss-cn-beijing"
        access_key = oss_token["accessKeyId"]
        secret_key = oss_token["accessKeySecret"]
        security_token = oss_token["securityToken"]

        oss_host = f"{bucket}.{region}.aliyuncs.com"
        oss_url_upload = f"https://{oss_host}/{oss_path}"
        oss_url_public = f"https://rain-{bucket}.xuetangx.com/{oss_path}"

        try:
            # 1. 初始化分片上传
            init_url = f"{oss_url_upload}?uploads"
            date_str = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            content_type = self._get_content_type(file_ext)

            signature = self._calculate_oss_signature(
                secret_key,
                "POST",
                f"/{bucket}/{oss_path}?uploads",
                date_str,
                security_token,
                content_type=content_type,
            )

            init_headers = {
                "Authorization": f"OSS {access_key}:{signature}",
                "x-oss-date": date_str,
                "x-oss-security-token": security_token,
                "Content-Type": content_type,
            }

            init_response = self.session.post(
                init_url, headers=init_headers, timeout=30
            )
            if init_response.status_code != 200:
                self._log(f"❌ 初始化上传失败: {init_response.text}")
                return None

            import xml.etree.ElementTree as ET

            root = ET.fromstring(init_response.content)
            upload_id = root.find(".//UploadId").text

            # 2. 上传文件分片
            part_url = f"{oss_url_upload}?partNumber=1&uploadId={upload_id}"
            date_str = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

            signature = self._calculate_oss_signature(
                secret_key,
                "PUT",
                f"/{bucket}/{oss_path}?partNumber=1&uploadId={upload_id}",
                date_str,
                security_token,
                content_type=content_type,
            )

            upload_headers = {
                "Authorization": f"OSS {access_key}:{signature}",
                "x-oss-date": date_str,
                "x-oss-security-token": security_token,
                "Content-Type": content_type,
            }

            upload_response = self.session.put(
                part_url, data=file_content, headers=upload_headers, timeout=30
            )
            if upload_response.status_code != 200:
                self._log(f"❌ 上传文件失败: {upload_response.text}")
                return None

            etag = upload_response.headers.get("ETag", "").strip('"')

            # 3. 完成上传
            complete_url = f"{oss_url_upload}?uploadId={upload_id}"
            complete_body = (
                f"<CompleteMultipartUpload><Part><PartNumber>1</PartNumber>"
                f"<ETag>{etag}</ETag></Part></CompleteMultipartUpload>"
            )
            complete_md5 = base64.b64encode(
                hashlib.md5(complete_body.encode()).digest()
            ).decode()

            date_str = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            signature = self._calculate_oss_signature(
                secret_key,
                "POST",
                f"/{bucket}/{oss_path}?uploadId={upload_id}",
                date_str,
                security_token,
                content_type="application/xml",
                content_md5=complete_md5,
            )

            complete_headers = {
                "Authorization": f"OSS {access_key}:{signature}",
                "x-oss-date": date_str,
                "x-oss-security-token": security_token,
                "Content-Type": "application/xml",
                "Content-MD5": complete_md5,
            }

            complete_response = self.session.post(
                complete_url, data=complete_body, headers=complete_headers, timeout=30
            )
            if complete_response.status_code != 200:
                self._log(f"❌ 完成上传失败: {complete_response.text}")
                return None

            self._log(f"✅ 文件上传成功: {file_name}")

            simple_type = file_ext.lstrip(".").lower() if file_ext else "file"

            return {
                "url": oss_url_public,
                "name": file_name,
                "size": file_size,
                "type": content_type,
                "md5": file_md5,
                "simple_type": simple_type,
            }

        except Exception as e:
            self._log(f"❌ 上传文件出错: {e}")
            raise

    def send_message_with_file(
        self, message: str, file_path: str, stream: bool = True
    ) -> Optional[str]:
        """
        发送带文件附件的消息
        """
        self._log(f"📎 正在上传文件: {file_path}")
        try:
            file_info = self.upload_file(file_path)
            if not file_info:
                self._log("❌ 文件上传失败，无法发送消息")
                return None
        except Exception:
            return None

        if not self.conversation_id:
            self._log("⚠️  没有对话 ID，尝试创建新对话...")
            try:
                conv_id = self.create_new_conversation()
                if not conv_id:
                    self._log(
                        "❌ 创建对话失败！请运行: uv run python tools/get_conversation_id.py"
                    )
                    return None
            except Exception:
                return None

        url = f"{self.base_url}/api/v3/ai/online-courseware/capability-conversation/send-message-stream"

        simple_type = file_info.get("simple_type", "file")

        data = {
            "messageInfo": {
                "templateId": 0,
                "source": 0,
                "content": message,
                "agentId": self.agent_id,
                "type": "talk",
                "searchId": "",
                "files": [],
                "source_id": 0,
                "attachments": [
                    {
                        "md5": file_info.get("md5", ""),
                        "name": file_info["name"],
                        "size": file_info["size"],
                        "type": simple_type,
                        "url": file_info["url"],
                        "file_parse_type": 1,
                    }
                ],
                "text": message,
                "id": 0,
                "multi": False,
                "quote_id": "",
                "quote_content": "",
                "_data": {},
                "workflow_id": self.workflow_id,
                "classroom_id": self.classroom_id,
            },
            "conversationId": int(self.conversation_id),
        }

        try:
            if stream:
                self._start_stream_buffer()
                response = self.session.post(url, json=data, stream=True, timeout=120)

                full_response = ""
                self._stream("🤖 AI: ")

                first_line = True
                for line in response.iter_lines():
                    if line:
                        try:
                            line_text = line.decode("utf-8")
                            chunk = json.loads(line_text)

                            if first_line and "reply_id" in chunk:
                                first_line = False
                                continue

                            if "content" in chunk:
                                text = chunk["content"]
                                if text:
                                    self._stream(text)
                                    full_response += text

                        except json.JSONDecodeError:
                            self._log(
                                f"⚠️ Warning: Failed to parse JSON chunk: {line[:50]}..."
                            )
                            continue
                        except Exception as e:
                            self._log(f"❌ Error processing chunk: {e}")
                            continue

                if self._logger is print:
                    print()
                else:
                    self._flush_stream_buffer()
                return full_response

            response = self.session.post(url, json=data, timeout=300)

            try:
                result = response.json()
                return result.get("data", {}).get("content", str(result))
            except json.JSONDecodeError:
                full_response = ""
                for line in response.text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(chunk, dict) and "content" in chunk:
                        text = chunk.get("content")
                        if text:
                            full_response += text
                if full_response:
                    return full_response
                return response.text or None

        except Exception as e:
            self._log(f"❌ 发送消息出错: {e}")
            raise

    def _get_content_type(self, file_ext: str) -> str:
        """获取文件的 Content-Type"""
        content_types = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
        }
        return content_types.get(file_ext.lower(), "application/octet-stream")

    def _calculate_oss_signature(
        self,
        secret: str,
        method: str,
        path: str,
        date: str,
        token: str,
        content_type: str = "",
        content_md5: str = "",
    ) -> str:
        """计算 OSS 签名"""
        import hmac
        import hashlib
        import base64

        string_to_sign = (
            f"{method}\n"
            f"{content_md5}\n"
            f"{content_type}\n"
            f"{date}\n"
            f"x-oss-date:{date}\n"
            f"x-oss-security-token:{token}\n"
            f"{path}"
        )
        signature = base64.b64encode(
            hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()
        return signature
