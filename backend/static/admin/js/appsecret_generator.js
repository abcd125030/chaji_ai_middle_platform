(function() {
    'use strict';

    function initAppsecretGenerator($) {
        // 绑定重新生成按钮的点击事件
        $(document).on('click', '.regenerate-appsecret', function(e) {
            e.preventDefault();

            // 发送 Ajax 请求获取新的 appsecret
            $.ajax({
                url: '/admin/service_api/externalservice/regenerate-appsecret/',
                type: 'GET',
                success: function(data) {
                    // 更新输入框的值
                    $('.appsecret-field').val(data.appsecret);
                },
                error: function(xhr, status, error) {
                    console.error("重新生成失败:", error);
                    alert("重新生成 appsecret 失败，请重试");
                }
            });
        });
    }

    // 等待 DOM 加载完成后，检查 django.jQuery 是否可用
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (typeof django !== 'undefined' && django.jQuery) {
                initAppsecretGenerator(django.jQuery);
            }
        });
    } else {
        // DOM 已加载完成
        if (typeof django !== 'undefined' && django.jQuery) {
            initAppsecretGenerator(django.jQuery);
        }
    }
})();
