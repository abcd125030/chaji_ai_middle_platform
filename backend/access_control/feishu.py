import secrets
import json
from urllib.parse import urlencode
from django.conf import settings
from .models import OAuthState

class FeishuLogin:
    """飞书登录工具类"""
    def generate_code_verifier(self):
        code_verifier = secrets.token_urlsafe(32)
        return code_verifier

    def get_feishu_auth_url(self, callback_url='', action=''):
        state = secrets.token_urlsafe(16)
        redirect_url = settings.FEISHU['OAUTH']['REDIRECT_URI']
        
        extra_data = {}
        if callback_url:
            extra_data['callback_url'] = callback_url
        if action:
            extra_data['action'] = action
            
        if extra_data:
            OAuthState.objects.create(
                state=state,
                extra_data=json.dumps(extra_data))
        else:
            OAuthState.objects.create(state=state)

        params = {
            'client_id': settings.FEISHU['APP_ID'],
            'response_type': 'code',
            'state': state,
            'redirect_uri': redirect_url,
        }
        return {
            'auth_url': f"{settings.FEISHU['OAUTH']['AUTHORIZATION_URL']}?{urlencode(params)}",
            'state': state
        }