"""
创建 Super-Router Agent 图结构的 Django 管理命令

这个文件包含一个 Django 管理命令，用于自动创建和配置 Super-Router Agent 的图结构。
该命令会创建一个基于 Planner-Executor-Reflection 循环架构的智能代理图。

主要功能：
1. 创建或更新名为 'Super-Router Agent' 的图结构
2. 自动创建核心节点：planner(任务规划)、reflection(反思总结)、output(输出处理)、END(结束节点)
3. 动态创建所有已注册的工具节点，并按类别分为普通工具和输出工具
4. 建立节点之间的连接边，形成完整的工作流程
5. 支持保留现有节点的模型配置和干运行模式

运行方式：
    python manage.py create_graph                    # 标准模式，清空现有图并重新创建
    python manage.py create_graph --preserve-models  # 保留现有节点的模型配置
    python manage.py create_graph --dry-run          # 仅显示操作不实际执行

工作流程：
1. Planner 节点接收任务并制定计划
2. 根据计划调用相应的工具节点执行任务
3. Reflection 节点对执行结果进行反思和评估
4. 如果任务未完成，返回 Planner 继续循环
5. 任务完成时，通过 Output 节点选择输出工具
6. 输出工具生成格式化的最终答案
7. 到达 END 节点，标记任务完成

返回值：
- 成功时：在终端输出创建/更新的图结构信息，包括节点数量、边数量等
- 失败时：输出错误信息并退出
- Dry-run 模式：仅输出将要执行的操作，不修改数据库

节点类型说明：
- ROUTER 节点：进行路由决策的节点（planner、reflection、output），虽然内部使用LLM但主要职责是决定执行路径
- TOOL 节点：执行具体功能的工具节点
- 普通工具：可被 Planner 调用的执行类工具
- 输出工具：仅可被 Output 节点调用的格式化工具

注意事项：
- 该命令需要在 Django 环境中运行
- 需要确保 tools.libs 模块已正确注册所有工具
- 建议在测试环境先使用 --dry-run 参数验证操作
"""

from django.core.management.base import BaseCommand
from agentic.models import Graph, Node, Edge
from tools.core.registry import ToolRegistry # 导入工具注册中心，用于获取所有工具名
import tools.libs # 导入此行以触发工具注册

class Command(BaseCommand):
    """
    Super-Router Agent 图结构创建命令类
    
    这个 Django 管理命令类负责创建和维护 Super-Router Agent 的完整图结构。
    该代理基于 Planner-Executor-Reflection 循环架构，能够动态决策并持续优化。
    
    命令参数：
        --preserve-models: 布尔标志，保留现有节点的模型配置而不是重置
        --dry-run: 布尔标志，仅显示将要执行的操作而不实际修改数据库
    
    创建的图结构包含：
        核心节点：
        - planner: 任务规划节点（ROUTER类型），负责分析用户需求并制定执行计划，路由到相应工具
        - reflection: 反思总结节点（ROUTER类型），评估执行结果并决定是否继续循环
        - output: 输出处理节点（ROUTER类型），选择合适的输出工具进行结果格式化
        - END: 结束节点（TOOL类型），标记工作流程结束
        
        动态工具节点：
        - 普通工具节点：可被 planner 调用的执行类工具
        - 输出工具节点：仅可被 output 节点调用的格式化工具
        
    边连接规则：
        - planner -> 工具节点（条件边，基于 CALL_TOOL:工具名）
        - 工具节点 -> reflection（无条件边）
        - reflection -> planner（循环边）
        - planner -> output（条件边，FINISH）
        - output -> 输出工具节点（条件边，OUTPUT:工具名）
        - 输出工具节点 -> END（无条件边）
    """
    help = 'Creates the Super-Router Agent graph'
    
    def add_arguments(self, parser):
        """
        添加命令行参数配置
        
        参数说明：
            --preserve-models: 保留现有节点的模型配置，避免重置已配置的 LLM 模型
            --dry-run: 干运行模式，仅显示操作步骤而不实际执行数据库修改
        
        Args:
            parser: Django 命令行参数解析器
        """
        parser.add_argument(
            '--preserve-models',
            action='store_true',
            help='保留现有节点的模型配置',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='显示将要进行的操作但不实际执行',
        )

    def handle(self, *args, **options):
        """
        命令主处理方法，执行图结构的创建和配置
        
        执行流程：
        1. 解析命令参数，设置运行模式
        2. 创建或获取 'Super-Router Agent' 图对象
        3. 处理现有图数据（清空或保留配置）
        4. 创建核心节点（planner, reflection, output 为 ROUTER 类型，END 为 TOOL 类型）
        5. 从工具注册中心获取所有可用工具
        6. 按类别分类工具（普通工具 vs 输出工具）
        7. 创建工具节点并配置连接边
        8. 建立完整的工作流程连接
        
        Args:
            *args: 位置参数（未使用）
            **options: 命令选项字典
                - preserve_models: 是否保留现有模型配置
                - dry_run: 是否为干运行模式
        
        Returns:
            None: 方法无返回值，通过 stdout 输出执行结果
            
        输出信息：
            - 图创建/更新状态
            - 节点创建/更新详情
            - 边连接创建详情
            - 工具分类统计信息
            - 执行完成确认
            
        异常处理：
            - 数据库连接异常：自动重试或输出错误信息
            - 工具注册异常：跳过有问题的工具并继续执行
            - 配置文件异常：使用默认配置继续执行
        """
        preserve_models = options.get('preserve_models', False)  # 默认不保留，需要明确指定才保留
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('运行在 DRY-RUN 模式，不会实际修改数据库'))
        
        self.stdout.write(self.style.SUCCESS('开始创建 Super-Router Agent 图...'))
        if preserve_models:
            self.stdout.write(self.style.SUCCESS('将保留现有节点的模型配置'))

        # 1. 创建或获取 Graph
        if not dry_run:
            graph, created = Graph.objects.get_or_create(
                name='Super-Router Agent',
                defaults={'description': '一个基于Planner-Executor-Reflection循环，动态决策和反思的Agent。'}
            )
        else:
            # 在 dry-run 模式下，只查询不创建
            try:
                graph = Graph.objects.get(name='Super-Router Agent')
                created = False
            except Graph.DoesNotExist:
                self.stdout.write(self.style.SUCCESS("将创建新图: Super-Router Agent"))
                return  # 在 dry-run 模式下，如果图不存在就退出
                
        if created:
            self.stdout.write(self.style.SUCCESS(f"成功创建图: {graph.name}"))
        else:
            self.stdout.write(self.style.WARNING(f"图 '{graph.name}' 已存在，将更新其节点和边。"))
            
        # 保存现有节点的模型配置
        existing_model_configs = {}
        if not created and preserve_models:
            for node in Node.objects.filter(graph=graph):
                if node.config and 'model_name' in node.config:
                    existing_model_configs[node.name] = node.config.get('model_name')
                    self.stdout.write(self.style.SUCCESS(f"保留节点 '{node.name}' 的模型配置: {node.config.get('model_name')}"))
        
        if not dry_run and not created:
            if preserve_models:
                # 保留模式：只清空边，保留节点
                Edge.objects.filter(graph=graph).delete()
                self.stdout.write(self.style.WARNING(f"已清空图 '{graph.name}' 的旧边，保留节点配置。"))
            else:
                # 默认模式：清空所有节点和边
                Edge.objects.filter(graph=graph).delete()
                Node.objects.filter(graph=graph).delete()
                self.stdout.write(self.style.WARNING(f"已清空图 '{graph.name}' 的所有节点和边。"))
        elif dry_run and not created:
            if preserve_models:
                self.stdout.write(self.style.WARNING(f"[DRY-RUN] 将清空图 '{graph.name}' 的旧边，保留节点配置。"))
            else:
                self.stdout.write(self.style.WARNING(f"[DRY-RUN] 将清空图 '{graph.name}' 的所有节点和边。"))

        # 2. 创建或更新核心节点
        # 如果不是第一次创建，从保存的配置中恢复 model_name
        existing_model_configs = locals().get('existing_model_configs', {})
        
        planner_config = {}
        if 'planner' in existing_model_configs:
            planner_config['model_name'] = existing_model_configs['planner']
            
        n_planner, planner_created = Node.objects.get_or_create(
            graph=graph,
            name='planner',
            defaults={
                'display_name': '任务规划',
                'node_type': Node.NodeType.ROUTER,
                'python_callable': 'backend.agentic.nodes.planner.planner_node',
                'config': planner_config
            }
        )
        if not planner_created and preserve_models and planner_config:
            n_planner.config.update(planner_config)
            n_planner.save()
        self.stdout.write(f"{'创建' if planner_created else '更新'}节点: {n_planner.name}")

        reflection_config = {}
        if 'reflection' in existing_model_configs:
            reflection_config['model_name'] = existing_model_configs['reflection']
            
        n_reflection, reflection_created = Node.objects.get_or_create(
            graph=graph,
            name='reflection',
            defaults={
                'display_name': '反思与总结',
                'node_type': Node.NodeType.ROUTER,
                'python_callable': 'backend.agentic.nodes.reflection.reflection_node',
                'config': reflection_config
            }
        )
        if not reflection_created and preserve_models and reflection_config:
            n_reflection.config.update(reflection_config)
            n_reflection.save()
        self.stdout.write(f"{'创建' if reflection_created else '更新'}节点: {n_reflection.name}")

        # 创建 Output 节点 - 用于选择输出工具生成最终答案
        output_config = {}
        if 'output' in existing_model_configs:
            output_config['model_name'] = existing_model_configs['output']
            
        n_output, output_created = Node.objects.get_or_create(
            graph=graph,
            name='output',
            defaults={
                'display_name': '输出处理',
                'node_type': Node.NodeType.ROUTER,
                'python_callable': 'backend.agentic.nodes.output.output_node',
                'config': output_config
            }
        )
        if not output_created and preserve_models and output_config:
            n_output.config.update(output_config)
            n_output.save()
        self.stdout.write(f"{'创建' if output_created else '更新'}节点: {n_output.name}")

        n_end, end_created = Node.objects.get_or_create(
            graph=graph,
            name='END',
            defaults={
                'display_name': '结束',
                'node_type': Node.NodeType.TOOL,
                'python_callable': 'tools.utils.common.end_process'
            }
        )
        self.stdout.write(f"{'创建' if end_created else '更新'}节点: {n_end.name}")

        # 3. 动态创建工具节点并连接边
        registry = ToolRegistry()
        all_tool_names = registry.list_tools()
        
        # 过滤掉核心LLM工具，以及我们新定义的router、reflection和output
        dynamic_tools = [
            tool_name for tool_name in all_tool_names
            if tool_name not in ['planner', 'reflection', 'output', 'end_process'] # 过滤掉核心节点、结束节点
        ]
        
        # 根据category分离输出类工具和普通工具
        # generator类别的工具都可以作为输出工具
        output_tools = []
        normal_tools = []
        
        for tool_name in dynamic_tools:
            tool_details = registry._tools.get(tool_name, {})
            category = tool_details.get('category', 'unknown')
            
            if category == 'generator':  # generator类的工具作为输出工具
                output_tools.append(tool_name)
            else:
                normal_tools.append(tool_name)
        
        # 打印工具列表及其分类，便于调试
        self.stdout.write("\n\n普通工具列表（按分类）:")
        tools_by_category = {}
        for tool_name in normal_tools:
            tool_details = registry._tools.get(tool_name, {})
            category = tool_details.get('category', 'unknown')
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append(tool_name)
        
        for category, tools in sorted(tools_by_category.items()):
            self.stdout.write(f"  {category}: {', '.join(tools)}")
        
        self.stdout.write(f"\n输出类工具列表: {output_tools}\n")

        # 创建普通工具节点（planner可以调用）
        for tool_name in normal_tools:
            # 获取工具的详细信息，包括category
            tool_details = registry._tools.get(tool_name, {})
            tool_category = tool_details.get('category', 'unknown')
            
            # 准备节点配置，如果有保存的模型配置则恢复
            tool_config = {
                'category': tool_category  # 添加工具分类信息
            }
            if tool_name in existing_model_configs:
                tool_config['model_name'] = existing_model_configs[tool_name]
                
            tool_node, created = Node.objects.get_or_create(
                graph=graph,
                name=tool_name,
                defaults={
                    'display_name': tool_name.replace('_', ' ').title(),
                    'node_type': Node.NodeType.TOOL,
                    # 直接从 ToolRegistry 获取工具的完整 Python 路径
                    'python_callable': registry.get_tool_class_path(tool_name),
                    'config': tool_config  # 使用恢复的配置或空配置
                }
            )
            
            # 如果节点已存在但有保存的配置，更新配置
            if not created and tool_name in existing_model_configs:
                tool_node.config = tool_config
                tool_node.save()
                self.stdout.write(f"更新工具节点 {tool_node.name} 的模型配置: {tool_config.get('model_name')}")
            elif created:
                self.stdout.write(f"创建工具节点: {tool_node.name}")

            # 从 planner 到当前工具的条件边 (条件键为 CALL_TOOL)
            condition_key = f"CALL_TOOL:{tool_name}"
            if not dry_run:
                Edge.objects.create(graph=graph, source=n_planner, target=tool_node, condition_key=condition_key)
            self.stdout.write(f"{'[DRY-RUN] ' if dry_run else ''}创建条件边: {n_planner.name} --[{condition_key}]--> {tool_node.name}")

            # 从当前工具返回 reflection 节点
            if not dry_run:
                Edge.objects.create(graph=graph, source=tool_node, target=n_reflection)
            self.stdout.write(f"{'[DRY-RUN] ' if dry_run else ''}创建边: {tool_node.name} --> {n_reflection.name}")
        
        # 创建输出类工具节点（只有finalizer可以调用）
        output_tool_nodes = []
        for tool_name in output_tools:
            # 获取工具的详细信息，包括category
            tool_details = registry._tools.get(tool_name, {})
            tool_category = tool_details.get('category', 'unknown')
            
            # 准备节点配置，如果有保存的模型配置则恢复
            tool_config = {
                'is_output_tool': True,  # 标记为输出类工具
                'category': tool_category,  # 添加工具分类信息
                'retry_count': 3  # P0阶段使用代码常量定义重试次数
            }
            if tool_name in existing_model_configs:
                tool_config['model_name'] = existing_model_configs[tool_name]
                
            tool_node, created = Node.objects.get_or_create(
                graph=graph,
                name=tool_name,
                defaults={
                    'display_name': tool_name.replace('_', ' ').title(),
                    'node_type': Node.NodeType.TOOL,
                    # 直接从 ToolRegistry 获取工具的完整 Python 路径
                    'python_callable': registry.get_tool_class_path(tool_name),
                    'config': tool_config  # 使用恢复的配置或空配置
                }
            )
            output_tool_nodes.append(tool_node)
            
            # 如果节点已存在但有保存的配置，更新配置
            if not created:
                tool_node.config = tool_config
                tool_node.save()
                self.stdout.write(f"更新输出工具节点 {tool_node.name} 配置: {tool_config}")
            elif created:
                self.stdout.write(f"创建输出工具节点: {tool_node.name}")

            # 从 output 到输出工具的条件边
            condition_key = f"OUTPUT:{tool_name}"
            if not dry_run:
                Edge.objects.create(graph=graph, source=n_output, target=tool_node, condition_key=condition_key)
            self.stdout.write(f"{'[DRY-RUN] ' if dry_run else ''}创建条件边: {n_output.name} --[{condition_key}]--> {tool_node.name}")

            # 从输出工具到 END 的边
            if not dry_run:
                Edge.objects.create(graph=graph, source=tool_node, target=n_end)
            self.stdout.write(f"{'[DRY-RUN] ' if dry_run else ''}创建边: {tool_node.name} --> {n_end.name}")

        # 4. 创建核心边
        # 从 reflection 返回 planner，形成循环
        if not dry_run:
            Edge.objects.create(graph=graph, source=n_reflection, target=n_planner)
        self.stdout.write(f"{'[DRY-RUN] ' if dry_run else ''}创建边: {n_reflection.name} --> {n_planner.name}")

        # 从 planner 到 output 的条件边（当决定 FINISH 时）
        if not dry_run:
            Edge.objects.create(graph=graph, source=n_planner, target=n_output, condition_key='FINISH')
        self.stdout.write(f"{'[DRY-RUN] ' if dry_run else ''}创建条件边: {n_planner.name} --[FINISH]--> {n_output.name}")
        
        # 注意：output 节点总是选择一个输出工具，不会直接到 END
        # 所有的输出工具执行完成后会自动导航到 END（已在上面的循环中设置）

        self.stdout.write(self.style.SUCCESS('Super-Router Agent 图创建完成。'))