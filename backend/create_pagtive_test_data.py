#!/usr/bin/env python
"""
创建 Pagtive 测试数据脚本
"""

import os
import sys
import django
import uuid
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/Users/chagee/Repos/X/backend')

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from webapps.pagtive.models import Project, ProjectDetail, ProjectLLMLog

User = get_user_model()

def create_test_data():
    # 获取或创建测试用户
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'testuser@example.com',
            'is_active': True
        }
    )
    
    if created:
        user.set_password('testpass123')
        user.save()
        print(f"创建测试用户: {user.username}")
    else:
        print(f"使用已存在用户: {user.username}")
    
    # 获取用户 ID 为 2 的用户（从你的JWT token解析出来的）
    try:
        actual_user = User.objects.get(id=2)
        print(f"找到实际用户: {actual_user.username} (ID: {actual_user.id})")
    except User.DoesNotExist:
        actual_user = user
        print("未找到 ID=2 的用户，使用测试用户")
    
    # 创建测试项目
    projects = []
    
    # 项目 1: 公司介绍演示
    project1 = Project.objects.create(
        user=actual_user,
        project_name="公司介绍演示",
        project_description="用于展示公司概况和业务介绍的演示文稿",
        project_style="modern",
        global_style_code="body { font-family: 'PingFang SC', sans-serif; }",
        pages=[
            {"id": 1, "title": "封面", "order": 0},
            {"id": 2, "title": "公司简介", "order": 1},
            {"id": 3, "title": "核心产品", "order": 2},
            {"id": 4, "title": "团队介绍", "order": 3},
            {"id": 5, "title": "联系我们", "order": 4}
        ],
        is_public=True,
        is_published=True,
        style_tags=[{"value": "modern"}, {"value": "professional"}],
        created_at=datetime.now() - timedelta(days=7),
        updated_at=datetime.now() - timedelta(days=2)
    )
    projects.append(project1)
    print(f"创建项目 1: {project1.project_name}")
    
    # 为项目1创建页面详情
    for page in project1.pages:
        ProjectDetail.objects.create(
            project=project1,
            page_id=page["id"],
            html=f'<div class="page"><h1>{page["title"]}</h1><p>这是{page["title"]}页面的内容</p></div>',
            styles='div.page { padding: 40px; text-align: center; }',
            script='console.log("Page loaded");'
        )
    print(f"  - 创建了 {len(project1.pages)} 个页面详情")
    
    # 项目 2: 产品发布会
    project2 = Project.objects.create(
        user=actual_user,
        project_name="2024 新品发布会",
        project_description="年度新产品发布会演示材料",
        project_style="creative",
        pages=[
            {"id": 1, "title": "开场", "order": 0},
            {"id": 2, "title": "产品亮点", "order": 1},
            {"id": 3, "title": "技术创新", "order": 2}
        ],
        is_public=False,
        style_tags=[{"value": "creative"}, {"value": "colorful"}],
        created_at=datetime.now() - timedelta(days=14),
        updated_at=datetime.now() - timedelta(hours=5)
    )
    projects.append(project2)
    print(f"创建项目 2: {project2.project_name}")
    
    # 项目 3: 教育培训材料
    project3 = Project.objects.create(
        user=actual_user,
        project_name="Python 入门教程",
        project_description="面向初学者的 Python 编程基础教程",
        project_style="simple",
        pages=[
            {"id": 1, "title": "课程介绍", "order": 0},
            {"id": 2, "title": "基础语法", "order": 1},
            {"id": 3, "title": "数据类型", "order": 2},
            {"id": 4, "title": "控制流程", "order": 3},
            {"id": 5, "title": "函数定义", "order": 4},
            {"id": 6, "title": "实战练习", "order": 5}
        ],
        is_public=True,
        is_featured=True,
        style_tags=[{"value": "simple"}, {"value": "elegant"}],
        created_at=datetime.now() - timedelta(days=30),
        updated_at=datetime.now() - timedelta(minutes=30)
    )
    projects.append(project3)
    print(f"创建项目 3: {project3.project_name}")
    
    # 项目 4: 季度报告
    project4 = Project.objects.create(
        user=actual_user,
        project_name="Q4 2024 业绩报告",
        project_description="第四季度业绩总结与分析",
        project_style="professional",
        pages=[
            {"id": 1, "title": "概述", "order": 0},
            {"id": 2, "title": "财务数据", "order": 1},
            {"id": 3, "title": "市场分析", "order": 2},
            {"id": 4, "title": "未来展望", "order": 3}
        ],
        is_public=False,
        style_tags=[{"value": "professional"}, {"value": "modern"}],
        created_at=datetime.now() - timedelta(hours=2),
        updated_at=datetime.now() - timedelta(minutes=5)
    )
    projects.append(project4)
    print(f"创建项目 4: {project4.project_name}")
    
    # 创建一些 LLM 日志记录
    for project in projects[:2]:  # 只为前两个项目创建日志
        ProjectLLMLog.objects.create(
            user=actual_user,
            project=project,
            page_id=1,
            provider="openai",
            model="gpt-4",
            scenario="generatePageCode",
            request_prompts={"prompt": f"生成{project.project_name}的内容"},
            request_config={"temperature": 0.7},
            response_content='{"html": "<div>Generated content</div>"}',
            status="success",
            usage_total_tokens=1500,
            duration_ms=2000
        )
    print(f"创建了 2 条 LLM 日志记录")
    
    print("\n✅ 测试数据创建完成！")
    print(f"共创建了 {len(projects)} 个项目")
    print(f"用户 ID: {actual_user.id}, 用户名: {actual_user.username}")
    
    return actual_user, projects

if __name__ == "__main__":
    user, projects = create_test_data()
    
    # 显示创建的项目列表
    print("\n项目列表：")
    for i, project in enumerate(projects, 1):
        print(f"{i}. {project.project_name} (ID: {project.id})")
        print(f"   - 页面数: {len(project.pages)}")
        print(f"   - 公开: {'是' if project.is_public else '否'}")
        print(f"   - 创建时间: {project.created_at}")