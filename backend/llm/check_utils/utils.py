import jwt
from django.utils import timezone
from access_control.models import UserLoginAuth
from router.models import VendorAPIKey
from service_api.models import ExternalService, UserAPIKey
from service_api.utils import JWTManager
import logging
import django
# 初始化 Django
django.setup()
logger = logging.getLogger(__name__)

# 用户信息缓存
# 统一缓存
service_cache = {}


# 检查token
def _check_token(auth_header):
    """
    文档：./check_token_flow.md
    检查并验证 JWT token，返回验证结果和用户信息
    """
    def _handle_error(error_msg):
        """统一处理错误日志和返回"""
        logger.error(error_msg)
        logger.info("check_token/结束执行")
        return error_msg, -1, "", ""

    logger.info("check_token/开始执行")
    logger.info(f"auth_header: {auth_header}")

    # 初始返回值
    result = None  # 初始为None，成功时才设为"success"
    service_appid = ""
    user_id = -1
    service_target = ""

    # 1. 检查 auth_header 格式
    if not auth_header or not auth_header.startswith('Bearer '):
        return _handle_error("ERR_AUTH_001: Invalid authorization header format")

    token = auth_header.replace('Bearer ', '')
    if not token:
        return _handle_error("ERR_AUTH_002: Empty token provided")

    try:
        # 2. 解码 JWT
        decoded_data = JWTManager.decode_token(token)

        # 3. 检查缓存
        if decoded_data['appid'] in service_cache:
            cached_data = service_cache[decoded_data['appid']]
            logger.info("从缓存中获取用户信息")
            return result, cached_data['user_id'], cached_data['service_target'], cached_data['service_appid']

        # 4. 验证服务注册信息
        try:
            service = ExternalService.objects.get(appid=decoded_data['appid'])
        except ExternalService.DoesNotExist:
            return _handle_error("ERR_USER_001: User service not registered")

        service_target = service.reason
        logger.info(f"service_target: {service_target}")

        # 5. 验证用户审核状态
        user_login_auth = UserLoginAuth.objects.filter(service_api=service).first()
        if not user_login_auth:
            return _handle_error("ERR_USER_002: No approval record found")
        if user_login_auth.result != "通过":
            return _handle_error("ERR_USER_003: User approval not granted")

        # 6. 获取用户信息并更新缓存
        user_id = service.user_id
        service_appid = service.appid
        service_cache[service_appid] = {
            'user_id': user_id,
            'service_target': service_target,
            'service_appid': service_appid,
            'llm_models': {}
        }
        logger.info("用户信息已缓存")

    except jwt.ExpiredSignatureError:
        return _handle_error("ERR_TOKEN_001: Token has expired")
    except jwt.InvalidTokenError:
        return _handle_error("ERR_TOKEN_002: Invalid token signature")
    except Exception as e:
        return _handle_error(f"ERR_SYS_001: Token decoding failed - {str(e)}")

    logger.info("check_token/结束执行")
    return result, user_id, service_target, service_appid


# 获取用户可以使用的大模型服务的接口和key
def get_used_llm_endpoint_key(service_appid):
    llm_model_dict = dict()
    
    # 检查缓存
    if service_appid in service_cache and 'llm_models' in service_cache[service_appid] and service_cache[service_appid]['llm_models']:
        logger.info("从缓存中获取大模型服务信息")
        return service_cache[service_appid]['llm_models']
        
    # 根据service获取用户模型审核的信息, 看看审批结论是不是通过, 通过的话则可以执行
    try:
        service = ExternalService.objects.get(appid=service_appid)
        for llm_model in service.llm_models.all():
            model_name = llm_model.name
            model_type = llm_model.model_type
            model_id = llm_model.model_id
            model_endpoint = llm_model.endpoint.endpoint
            model_vendor_name = llm_model.endpoint.vendor_name
            custom_headers = llm_model.custom_headers
            params = llm_model.params
            model_key = ""
            try:
                vendorAPIKeySet = VendorAPIKey.objects.filter(vendor_name=model_vendor_name)
                if vendorAPIKeySet:
                    model_key = VendorAPIKey.objects.get(vendor_name=model_vendor_name).api_key
            except VendorAPIKey.DoesNotExist:
                logger.error(f"No API key found for vendor: {model_vendor_name}")
                model_key = ""
            except Exception as e:
                logger.error(f"Unexpected error retrieving API key: {str(e)}")
                model_key = ""
            llm_model_dict[model_name] = {'model_endpoint': model_endpoint, 'model_key': model_key,
                                          "model_id": model_id, "model_type": model_type,
                                          "custom_headers": custom_headers, "params": params}
        # 更新缓存
        if service_appid in service_cache:
            service_cache[service_appid]['llm_models'] = llm_model_dict
            logger.info("大模型服务信息已缓存")
    except ExternalService.DoesNotExist:
        logger.error(f"No external service found for user ID: {service_appid}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving external service: {str(e)}")
        
    return llm_model_dict


def check_token_and_get_llm(ip_address, auth_header):
    llm_model_dict = dict()

    # 用户服务器的公网地址
    logger.info("REMOTE_ADDR: " + str(ip_address))

    # 步骤1: 检查token
    check_result, user_id, service_target, service_appid = _check_token(auth_header)

    if check_result is not None:
        result = {'error': '该用户没有通过token审核'}
        return result, llm_model_dict, user_id, service_target, service_appid
    
    if user_id == -1:
        result = {'error': '没有为该用户建立外部服务机制(Service_Api)'}
        return result, llm_model_dict, user_id, service_target, service_appid
    # 步骤2: 获取用户可以使用的大模型服务的接口和key
    llm_model_dict = get_used_llm_endpoint_key(service_appid)
    if len(llm_model_dict) <= 0:
        result = {'error': '没有为该用户绑定可以使用的大模型服务的接口和key'}
        return result, llm_model_dict, user_id, service_target, service_appid
    # 步骤3: 输出结果
    result = {'success': '该用户通过token审核, 该用户找到可以使用的大模型服务的接口和key'}
    return result, llm_model_dict, user_id, service_target, service_appid


def check_dual_auth_and_get_llm(ip_address, auth_header, request_data=None):
    """
    Triple-path authentication: API Key, JWT token, and appid/secret

    Args:
        ip_address: Client IP address
        auth_header: Authorization header
        request_data: Request data (for appid/secret auth)

    Returns:
        tuple: (result, llm_model_dict, user_id, service_target, service_appid)
    """
    llm_model_dict = dict()
    logger.info("REMOTE_ADDR: " + str(ip_address))

    # Path 1: API Key authentication (Bearer sk-xxx)
    if auth_header and auth_header.startswith('Bearer sk-'):
        logger.info("Attempting API Key authentication")
        api_key = auth_header.replace('Bearer ', '')

        auth_result = _check_api_key(api_key)
        if auth_result[1] == 200:
            user_id, service_target, api_key_id = auth_result[0]
            llm_model_dict = get_user_llm_permissions(user_id)
            if len(llm_model_dict) > 0:
                result = {'success': 'User authenticated via API Key'}
                return result, llm_model_dict, user_id, service_target, api_key_id
            else:
                result = {'error': 'No LLM models configured for this user'}
                return result, llm_model_dict, user_id, service_target, api_key_id
        else:
            result = auth_result[0]
            return result, llm_model_dict, -1, "", ""

    # Path 2: JWT token authentication
    if auth_header and auth_header.startswith('Bearer '):
        logger.info("尝试JWT token认证")
        check_result, user_id, service_target, service_appid = _check_token(auth_header)

        if check_result is None and user_id != -1:
            # JWT auth successful
            llm_model_dict = get_used_llm_endpoint_key(service_appid)
            if len(llm_model_dict) > 0:
                result = {'success': '该用户通过JWT token认证'}
                return result, llm_model_dict, user_id, service_target, service_appid

    # Path 3: appid/secret authentication
    if request_data and 'appid' in request_data and 'secret' in request_data:
        logger.info("尝试appid/secret认证")
        appid = request_data.get('appid')
        secret = request_data.get('secret')

        auth_result = _check_appid_secret(appid, secret)
        if auth_result[1] == 200:
            user_id, service_target, service_appid = auth_result[0]
            llm_model_dict = get_used_llm_endpoint_key(service_appid)
            if len(llm_model_dict) > 0:
                result = {'success': '该用户通过appid/secret认证'}
                return result, llm_model_dict, user_id, service_target, service_appid
            else:
                result = {'error': '没有为该用户绑定可以使用的大模型服务的接口和key'}
                return result, llm_model_dict, user_id, service_target, service_appid
        else:
            result = auth_result[0]
            return result, llm_model_dict, -1, "", ""

    # All authentication methods failed
    result = {'error': 'Authentication failed: provide valid API Key, JWT token, or appid/secret'}
    return result, llm_model_dict, -1, "", ""


def _check_appid_secret(appid, secret):
    """
    检查appid和secret认证
    
    Args:
        appid: 应用ID
        secret: 应用密钥
    
    Returns:
        tuple: ((user_id, service_target, service_appid), status_code) 或 (error_dict, status_code)
    """
    try:
        # 查找外部服务
        service = ExternalService.objects.get(appid=appid)
        
        # 验证secret
        if service.secret != secret:
            logger.error(f"Secret验证失败: appid={appid}")
            return {"error": "Invalid appid or secret"}, 401
        
        # 验证用户审核状态
        user_login_auth = UserLoginAuth.objects.filter(service_api=service).first()
        if not user_login_auth:
            logger.error(f"未找到审核记录: appid={appid}")
            return {"error": "No approval record found"}, 401
        
        if user_login_auth.result != "通过":
            logger.error(f"用户审核未通过: appid={appid}, result={user_login_auth.result}")
            return {"error": "User approval not granted"}, 401
        
        # 返回用户信息
        user_id = service.user_id
        service_target = service.reason
        service_appid = service.appid
        
        logger.info(f"appid/secret认证成功: user_id={user_id}, appid={appid}")
        return (user_id, service_target, service_appid), 200
        
    except ExternalService.DoesNotExist:
        logger.error(f"外部服务不存在: appid={appid}")
        return {"error": "Invalid appid or secret"}, 401
    except Exception as e:
        logger.error(f"appid/secret认证异常: {e}")
        return {"error": "Authentication failed"}, 500


def _check_api_key(api_key: str):
    """
    Validate API Key and return user info

    Args:
        api_key: The full API key (sk-xxx format)

    Returns:
        tuple: ((user_id, service_target, api_key_id), status_code) or (error_dict, status_code)
    """
    if not api_key or not api_key.startswith('sk-'):
        logger.error("Invalid API key format")
        return {"error": "Invalid API key format"}, 401

    # Hash the key for comparison
    key_hash = UserAPIKey.hash_key(api_key)

    try:
        api_key_record = UserAPIKey.objects.select_related('user').get(
            key_hash=key_hash,
            status=UserAPIKey.Status.ACTIVE
        )

        # Update last used time
        api_key_record.last_used_at = timezone.now()
        api_key_record.save(update_fields=['last_used_at'])

        user_id = api_key_record.user_id
        service_target = 'api_key_access'  # Default service target for API key

        logger.info(f"API Key authentication successful: user_id={user_id}, api_key_id={api_key_record.id}")
        return (user_id, service_target, str(api_key_record.id)), 200

    except UserAPIKey.DoesNotExist:
        logger.error("API Key not found or revoked")
        return {"error": "Invalid or revoked API key"}, 401
    except Exception as e:
        logger.error(f"API Key authentication error: {e}")
        return {"error": "Authentication failed"}, 500


def get_user_llm_permissions(user_id: int):
    """
    Get all LLM models a user has permission to use.
    Based on their ExternalService configurations.

    Args:
        user_id: The user's ID

    Returns:
        dict: Model name -> config mapping
    """
    llm_model_dict = dict()

    try:
        # Get all external services for this user
        services = ExternalService.objects.filter(user_id=user_id)

        for service in services:
            for llm_model in service.llm_models.all():
                model_name = llm_model.name
                model_type = llm_model.model_type
                model_id = llm_model.model_id
                model_endpoint = llm_model.endpoint.endpoint
                model_vendor_name = llm_model.endpoint.vendor_name
                custom_headers = llm_model.custom_headers
                params = llm_model.params

                # Get API key for vendor
                model_key = ""
                try:
                    vendor_key = VendorAPIKey.objects.filter(vendor_name=model_vendor_name).first()
                    if vendor_key:
                        model_key = vendor_key.api_key
                except Exception as e:
                    logger.error(f"Error getting vendor API key: {e}")

                llm_model_dict[model_name] = {
                    'model_endpoint': model_endpoint,
                    'model_key': model_key,
                    'model_id': model_id,
                    'model_type': model_type,
                    'custom_headers': custom_headers,
                    'params': params
                }

    except Exception as e:
        logger.error(f"Error getting user LLM permissions: {e}")

    return llm_model_dict
