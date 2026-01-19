from django.urls import path

from customized.customization.views import public_sentiment_analysis_service, public_sentiment_result_service, \
    batch_public_sentiment_analysis_service, batch_public_sentiment_result_service, \
    public_sentiment_pending_analysis_service

urlpatterns = [
    path('public_sentiment/handler/', public_sentiment_analysis_service, name='public_sentiment_analysis_service'),  # 接受用户输入的大模型指令，返回结果
    path('public_sentiment/batch_handler/', batch_public_sentiment_analysis_service, name='batch_public_sentiment_analysis_service'),  # 新增批量处理接口
    path('public_sentiment/result/', public_sentiment_result_service, name='public_sentiment_result_service'),  # 接受用户输入的查询指令，返回结果
    path('public_sentiment/batch_result/', batch_public_sentiment_result_service, name='batch_public_sentiment_result'),  # 接受用户输入的查询指令，返回批量处理结果
    path('public_sentiment/clear_pending/', public_sentiment_pending_analysis_service, name='public_sentiment_pending_analysis_service'),  # 接受用户输入的清除缓存pending文件中没执行的json
]
