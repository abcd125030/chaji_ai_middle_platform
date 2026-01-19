from django.db import models

from authentication.models import User
from router.models import LLMModel
from service_api.models import ExternalService

# def get_default_service_api():
#     # 这里编写逻辑获取默认的ExternalService对象，例如获取第一个对象
#     return ExternalService.objects.first().id


# Create your models here.
class UserLoginAuth(models.Model):
    """存储飞书用户的认证信息"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_check',
        verbose_name='关联用户'
    )

    service_api = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        related_name='service_api_check',
        verbose_name='关联外部服务',
        null=True,
        blank=True,
    )

    address = models.CharField(
        max_length=200,
        verbose_name='服务器IP地址'
    )
    reason = models.CharField(
        max_length=2000,
        verbose_name='申请原因'
    )

    RESULT_CHOICES = [
        ('审核中', '审核中'),
        ('通过', '通过'),
        ('驳回', '驳回'),
    ]

    result = models.CharField(
        max_length=100,
        verbose_name='审批结论',
        choices=RESULT_CHOICES,  # 添加 choices 参数
        default="审核中"  # 添加默认值
    )

    task = models.CharField(
        max_length=2000,
        verbose_name='业务名称',
        default='合同审核'
    )

    llm_models = models.ManyToManyField(  # 修改为 ManyToManyField
        LLMModel,
        related_name='llm_check',
        verbose_name='关联大语言模型',
        blank=True  # 允许为空
    )

    class Meta:
        verbose_name = '用户模型审核'
        verbose_name_plural = '用户模型审核'
