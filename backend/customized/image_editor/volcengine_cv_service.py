import json
import requests
import logging
import hashlib
import hmac
from datetime import datetime, timezone as tz
from urllib.parse import quote

logger = logging.getLogger(__name__)


class VolcengineCVService:
    """火山引擎CV服务客户端，用于调用主体分割等API"""
    
    def __init__(self, access_key, secret_key):
        """
        初始化火山引擎CV服务客户端
        
        Args:
            access_key (str): 火山引擎Access Key
            secret_key (str): 火山引擎Secret Key
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.host = "visual.volcengineapi.com"
        self.region = "cn-north-1"
        self.service = "cv"
        self.version = "2022-08-31"
        
    def _sign_request(self, method, path, headers, params, body):
        """
        生成火山引擎API签名
        
        参考测试用例中经过验证的签名算法
        """
        # 获取当前时间
        now = datetime.now(tz.utc)
        date_stamp = now.strftime('%Y%m%d')
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        
        # 准备签名所需的headers
        headers['X-Date'] = amz_date
        headers['Host'] = self.host
        headers['X-Content-Sha256'] = hashlib.sha256(body.encode('utf-8')).hexdigest()
        
        # 构建规范请求
        canonical_uri = path
        
        # 构建规范查询字符串
        canonical_querystring = '&'.join([f"{k}={quote(str(v), safe='')}" for k, v in sorted(params.items())])
        
        # 构建规范头部 - 只包含特定的头部用于签名
        canonical_headers = []
        signed_headers = []
        for key in sorted(headers.keys()):
            lower_key = key.lower()
            if lower_key in ['host', 'x-date', 'x-content-sha256', 'content-type']:
                canonical_headers.append(f"{lower_key}:{headers[key]}")
                signed_headers.append(lower_key)
        canonical_headers_str = '\n'.join(canonical_headers) + '\n'
        signed_headers_str = ';'.join(signed_headers)
        
        # 构建规范请求
        canonical_request = '\n'.join([
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers_str,
            signed_headers_str,
            headers['X-Content-Sha256']
        ])
        
        # 构建待签名字符串
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/request"
        string_to_sign = '\n'.join([
            'HMAC-SHA256',
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        ])
        
        # 计算签名 - 注意：不使用AWS4前缀，直接使用secret_key
        k_secret = self.secret_key.encode('utf-8')  # 直接使用secret_key，不加前缀
        k_date = hmac.new(k_secret, date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self.region.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, self.service.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b'request', hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # 构建Authorization头
        headers['Authorization'] = (
            f"HMAC-SHA256 "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, "
            f"Signature={signature}"
        )
        
        return headers
    
    def remove_background(self, image_url):
        """
        调用主体分割API去除背景
        
        Args:
            image_url (str): 输入图片URL
            
        Returns:
            dict: 包含处理结果的字典，格式为 {"success": bool, "image_base64": str, "error": str}
        """
        try:
            # 构建请求参数
            params = {
                "Action": "CVProcess",
                "Version": self.version
            }
            
            # 构建请求体
            body_data = {
                "req_key": "saliency_seg",
                "image_urls": [image_url],
                "only_mask": 3,  # 返回原图大小的BGRA透明前景图
                "rgb": [-1, -1, -1],  # 透明背景
                "refine_mask": 0,  # 不进行边缘增强（可根据需要调整）
                "return_url": True
            }
            body = json.dumps(body_data)
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            # 签名请求
            headers = self._sign_request("POST", "/", headers, params, body)
            
            # 构建完整URL
            url = f"https://{self.host}/?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
            
            logger.info(f"开始背景移除处理，图片URL: {image_url}")
            
            # 发送请求 - 减少超时时间避免连接池超时
            response = requests.post(url, headers=headers, data=body, timeout=20)
            
            # 记录完整响应信息用于调试
            if response.status_code != 200:
                logger.error(f"背景移除API请求失败 - 状态码: {response.status_code}")
                logger.error(f"Error details - Response body: {response.text if response.text else 'No response body'}")
                logger.error(f"Error details - Request URL: {url}")
                logger.error(f"Error details - Request body: {body}")
            
            response.raise_for_status()
            
            result = response.json()
            # 日志打印 result
            # logger.info(f"背景移除API响应: {result}")

            
            # 检查响应状态
            if result.get("code") == 10000 and result.get("status") == 10000:
                # 成功
                data = result.get("data", {})
                if "binary_data_base64" in data and len(data["binary_data_base64"]) > 0:
                    image_base64 = data["binary_data_base64"][0]
                    # image_url = data["image_urls"][0]   #该字段不再被官方api支持
                    logger.info(f"背景移除成功，结果大小: {len(image_base64)} 字符")
                    return {
                        "success": True,
                        "image_base64": image_base64,
                        # "image_url": image_url,   #该字段不再被官方api支持
                        "bbox": data.get("bbox", [[]])[0] if data.get("bbox") else None,
                        "seg_score": data.get("seg_score", [0])[0] if data.get("seg_score") else 0
                    }
                else:
                    logger.error("背景移除API返回数据中没有图片")
                    return {"success": False, "error": "背景移除结果为空"}
            else:
                # 失败
                error_msg = result.get("message", "未知错误")
                error_code = result.get("code", "")
                
                # 特殊错误处理
                if error_code == 61003 or "do not contain segment object" in error_msg:
                    logger.warning(f"图片中不包含可分割的主体: {error_msg}")
                    return {"success": False, "error": "未检测到可分割的主体"}
                else:
                    logger.error(f"背景移除失败: {error_msg} (code: {error_code})")
                    return {"success": False, "error": f"背景移除失败: {error_msg}"}
                    
        except requests.exceptions.Timeout as e:
            logger.error(f"背景移除API请求超时: {e}")
            logger.error(f"Error details - Request URL: {url if 'url' in locals() else 'URL not available'}")
            logger.error(f"Error details - Timeout value: 60 seconds")
            return {"success": False, "error": "背景移除超时", "error_type": "timeout", "details": str(e)}
        except requests.exceptions.RequestException as e:
            logger.error(f"背景移除API请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Error details - Status code: {e.response.status_code}")
                logger.error(f"Error details - Response body: {e.response.text if e.response.text else 'No response body'}")
                logger.error(f"Error details - Request URL: {url if 'url' in locals() else 'URL not available'}")
            return {"success": False, "error": f"背景移除请求失败: {str(e)}", "details": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"背景移除API响应JSON解析失败: {e}")
            logger.error(f"Error details - Response text: {response.text if 'response' in locals() and response.text else 'Response not available'}")
            return {"success": False, "error": f"背景移除响应解析失败: {str(e)}", "details": str(e)}
        except Exception as e:
            logger.error(f"背景移除过程发生异常: {e}")
            logger.error(f"Error details - Exception type: {type(e).__name__}")
            logger.error(f"Error details - Request URL: {url if 'url' in locals() else 'URL not available'}")
            return {"success": False, "error": f"背景移除异常: {str(e)}", "details": str(e)}