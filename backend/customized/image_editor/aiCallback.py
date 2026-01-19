import requests
import time
import uuid
import hashlib
import base64
import logging

# 尝试导入提示词配置
try:
    from .prompts_config import DEFAULT_TEST_PROMPT
except ImportError:
    # 如果配置文件不存在，使用默认值
    DEFAULT_TEST_PROMPT = "测试提示词"

logger = logging.getLogger(__name__)

class AICallback:
    def __init__(self, env='dev', callback_url=None):
        """
        初始化AI回调测试器
        
        Args:
            env (str): 环境，可选值：'dev', 'uat', 'prod'
            callback_url (str): 可选的回调URL，如果提供则使用此URL而非默认环境URL
        """
        # 设置环境和对应的URL
        self.env = env
        self.env_urls = {
            'dev': 'https://dev-game-center.chagee.com/game-cute-pet-biz',
            'uat': 'https://uat-game-center.chagee.com/game-cute-pet-biz',
            'prod': 'http://game-center.bwcj.biz/game-cute-pet-biz'   # 内网地址
        }
        
        # 设置密钥
        self.secret_keys = {
            'dev': '58ce60354e1d4d37b6b2bbf96c2fd88e',
            'uat': '58ce60354e1d4d37b6b2bbf96c2fd88e',  # 假设UAT环境使用相同的测试密钥
            'prod': 'd33a35fe73364ec4ac06b3ac3937cbfe'  # 生产环境密钥待提供
        }
        
        # 如果提供了callback_url，尝试从URL推断环境
        if callback_url:
            self.callback_url = callback_url
            # 从callback_url推断环境
            if 'dev-game-center' in callback_url:
                self.env = 'dev'
            elif 'uat-game-center' in callback_url:
                self.env = 'uat'
            elif 'game-center.bwcj.biz' in callback_url and 'dev-' not in callback_url and 'uat-' not in callback_url:
                self.env = 'prod'
            # 如果无法推断，保持传入的env参数
            
            self.base_url = self.env_urls.get(self.env)
            self.secret_key = self.secret_keys.get(self.env)
        else:
            # 使用默认环境配置
            self.base_url = self.env_urls.get(env)
            self.secret_key = self.secret_keys.get(env)
            
            if not self.base_url or not self.secret_key:
                raise ValueError(f"不支持的环境: {env}")
            
            # 设置默认回调接口地址
            self.callback_url = f"{self.base_url}/api/callback/aiImg"
        
        logger.info(f"初始化AI回调测试器，环境: {self.env}, 回调URL: {self.callback_url}")
    
    def generate_signature(self, nonce, timestamp):
        """
        生成签名
        
        Args:
            nonce (str): 随机字符串
            timestamp (str): 时间戳
            
        Returns:
            str: 生成的签名
        """
        # 按照规则拼接字符串
        sign_str = f"nonce={nonce}&secretKey={self.secret_key}&timestamp={timestamp}"
        
        # 使用SHA-256算法签名
        hash_obj = hashlib.sha256(sign_str.encode('utf-8'))
        signature = base64.b64encode(hash_obj.digest()).decode('utf-8')
        
        logger.info(f"生成签名: {signature}")
        return signature
    
    
    def create_success_callback_data(self, callback_data, prompt=None):
        """
        创建成功回调数据
        
        Args:
            callback_data (dict): 包含任务信息的字典，包含task_id、status、result_image、processing_time等
            prompt (str): 原始提示词
            
        Returns:
            dict: 回调数据
        """
        # 使用配置中的默认提示词
        if prompt is None:
            prompt = DEFAULT_TEST_PROMPT
            
        # 从callback_data中提取信息
        task_id = callback_data.get("task_id")
        image_data = callback_data.get("result_image")
        processing_time = callback_data.get("processing_time", 25.6)
        
        # 获取当前时间戳（毫秒级）
        current_timestamp = int(time.time() * 1000)
        timestamp_str = str(current_timestamp)
        
        # 获取当前时间的ISO格式字符串（包含毫秒）
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        
        # 使用用户给的11886
        nonce = 11886
        
        # 生成签名
        signature = self.generate_signature(nonce, timestamp_str)
        
        # 创建回调数据
        callback_data = {
            "params": {
                "code": 0,
                "data": {
                    "task_id": task_id,
                    "status": "success",
                    "data": {
                        "image": image_data,
                        "original_prompt": prompt
                    },
                    "processing_time": processing_time,
                    "created_at": current_time,
                    "completed_at": current_time
                },
                "message": "success",
                "timestamp": current_timestamp
            },
            "timestamp": timestamp_str,
            "signature": signature,
            "nonce": nonce
        }

        # 创建一个用于日志的深拷贝，避免修改原始数据
        import copy
        log_data = copy.deepcopy(callback_data)
        if 'params' in log_data and 'data' in log_data['params'] and 'data' in log_data['params']['data']:
            if 'image' in log_data['params']['data']['data']:
                image_value = log_data['params']['data']['data']['image']
                if image_value and len(image_value) > 100:
                    log_data['params']['data']['data']['image'] = f"{image_value[:50]}...[truncated {len(image_value)} chars]...{image_value[-50:]}"
        
        logger.info(f"Sending callback data: {log_data}")
        
        return callback_data

    def create_failed_callback_data(self, callback_data, prompt="测试提示词"):
        """
        创建失败回调数据
        
        Args:
            callback_data (dict): 包含任务信息的字典，包含task_id、error_code、error_message、error_details等
            error_code (str): 错误代码
            error_message (str): 错误信息
            
        Returns:
            dict: 回调数据
        """
        # 从callback_data中提取信息
        task_id = callback_data.get("task_id")
        error_code = callback_data.get("error_code")
        error_message = callback_data.get("error_message")
        error_details = callback_data.get("error_details")
        completed_at = callback_data.get("completed_at")
        
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 获取当前时间戳（毫秒级）
        current_timestamp = int(time.time() * 1000)
        timestamp_str = str(current_timestamp)
        
        # 获取当前时间的ISO格式字符串（包含毫秒）
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        
         # 使用用户给的11886
        nonce = 11886
        
        # 生成签名
        signature = self.generate_signature(nonce, timestamp_str)
        
        # 从错误码中提取数字部分作为顶层 code
        # 如果错误码以 'E' 开头，去掉 'E' 前缀
        top_level_code = int(error_code[1:]) if error_code and error_code.startswith('E') else 1006
        
        # 创建回调数据
        callback_data = {
            "params": {
                "code": top_level_code,
                "data": {
                    "task_id": task_id,
                    "status": "failed",
                    "error": {
                        "code": error_code,
                        "message": error_message,
                        "details": error_details
                    },
                    "created_at": current_time,
                    "completed_at": completed_at if completed_at else current_time
                },
                "message": error_message,
                "timestamp": current_timestamp
            },
            "timestamp": timestamp_str,
            "signature": signature,
            "nonce": nonce
        }
        
        logger.info(f"Sending failed callback data: {callback_data}")
        
        return callback_data
    
    def send_callback(self, callback_data, callback_url=None):
        """
        发送回调请求
        
        Args:
            callback_data (dict): 回调数据
            callback_url (str): 可选的自定义回调URL，如果不提供则使用默认URL
            
        Returns:
            requests.Response: 响应对象
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        # 使用提供的callback_url或默认的self.callback_url
        url = callback_url if callback_url else self.callback_url
        
        try:
            logger.info(f"发送回调请求到: {url}")
            # 创建一个用于日志的深拷贝，避免修改原始数据
            import copy
            log_data = copy.deepcopy(callback_data)
            if 'params' in log_data and 'data' in log_data['params'] and 'data' in log_data['params']['data']:
                if 'image' in log_data['params']['data']['data']:
                    image_value = log_data['params']['data']['data']['image']
                    if image_value and len(str(image_value)) > 100:
                        log_data['params']['data']['data']['image'] = f"{str(image_value)[:50]}...[truncated]..."
            logger.info(f"回调数据: {log_data}")
            response = requests.post(url, headers=headers, json=callback_data, timeout=30)
            
            logger.info(f"回调响应状态码: {response.status_code}")
            logger.info(f"回调响应内容: {response.text}")
            
            return response
        except Exception as e:
            logger.error(f"发送回调请求失败: {e}")
            return None