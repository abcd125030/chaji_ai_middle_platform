"""
初始化Pagtive默认配置
创建包含默认提示词的配置集
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from webapps.pagtive.models import PagtiveConfig, PagtivePromptTemplate
from webapps.pagtive.prompts import SYSTEM_PROMPTS
from router.models import LLMModel


class Command(BaseCommand):
    help = '初始化Pagtive默认配置，包含完整的提示词模板'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建配置（删除现有的默认配置）',
        )
        parser.add_argument(
            '--activate',
            action='store_true',
            help='创建后自动激活该配置',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        activate = options.get('activate', False)
        
        config_name = "默认配置（旧系统兼容）"
        
        # 检查是否已存在默认配置
        existing_config = PagtiveConfig.objects.filter(name=config_name).first()
        
        if existing_config and not force:
            self.stdout.write(
                self.style.WARNING(f'配置 "{config_name}" 已存在，使用 --force 参数可重新创建')
            )
            return
        
        if existing_config and force:
            self.stdout.write(self.style.WARNING(f'删除现有配置: {config_name}'))
            existing_config.delete()
        
        try:
            with transaction.atomic():
                # 创建配置
                self.stdout.write('创建Pagtive配置...')
                config = PagtiveConfig.objects.create(
                    name=config_name,
                    description="与旧Pagtive系统完全兼容的默认配置，包含完整的系统提示词和页面生成/编辑模板",
                    is_active=activate,
                    # LLM模型可以稍后在Admin中选择
                    llm_model=None,
                    llm_model_for_edit=None,
                    # 不在这里设置提示词，而是通过PagtivePromptTemplate管理
                    system_prompt="",
                    generate_template="",
                    edit_template="",
                    temperature=0.7,
                    max_tokens=None,  # 无限制
                    enable_stream=False,
                    extra_config={}
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 创建配置: {config.name}')
                )
                
                # 创建所有提示词模板
                templates = [
                    {
                        'name': '系统提示词',
                        'template_type': 'system',
                        'template_content': SYSTEM_PROMPTS['defaultAssistant'],
                        'order': 1,
                        'variables': [],
                    },
                    {
                        'name': '生成页面用户提示词',
                        'template_type': 'generate',
                        'template_content': self.get_generate_template(),  # 直接使用内联模板
                        'order': 2,
                        'variables': ['projectStyle', 'globalStyleCode', 'projectDescription', 
                                     'referenceHtml', 'referenceCss', 'referenceJs', 'requirement'],
                    },
                    {
                        'name': '编辑页面用户提示词',
                        'template_type': 'edit',
                        'template_content': self.get_edit_template(),  # 直接使用内联模板
                        'order': 3,
                        'variables': ['projectStyle', 'globalStyleCode', 'projectDescription',
                                     'currentHtml', 'currentCss', 'currentJs', 'currentMermaid',
                                     'referenceHtml', 'referenceCss', 'referenceJs', 'requirement'],
                    },
                    {
                        'name': '元数据生成',
                        'template_type': 'metadata',
                        'template_content': self.get_metadata_template(),  # 使用新的模板方法
                        'order': 4,
                        'variables': ['html_content'],
                    },
                    {
                        'name': '样式生成',
                        'template_type': 'style',
                        'template_content': self.get_style_template(),  # 使用新的模板方法
                        'order': 5,
                        'variables': ['styleDescription'],
                    },
                ]
                
                for tmpl_data in templates:
                    template = PagtivePromptTemplate.objects.create(
                        config=config,
                        name=tmpl_data['name'],
                        template_type=tmpl_data['template_type'],
                        template_content=tmpl_data['template_content'],
                        is_active=True,
                        order=tmpl_data['order'],
                        variables=tmpl_data.get('variables', [])
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'  + 创建模板: {template.name}')
                    )
                
                # 尝试查找并关联默认的LLM模型
                try:
                    default_llm = LLMModel.objects.filter(model_type='text').first()
                    if default_llm:
                        config.llm_model = default_llm
                        config.save()
                        self.stdout.write(
                            self.style.SUCCESS(f'  + 关联LLM模型: {default_llm.name}')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING('  ! 未找到可用的LLM模型，请在Admin中手动配置')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ! 无法自动关联LLM模型: {e}')
                    )
                
                if activate:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ 配置已激活: {config.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'配置已创建但未激活，请在Admin中手动激活或使用 --activate 参数'
                        )
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n成功初始化Pagtive配置！\n'
                        f'配置名称: {config.name}\n'
                        f'配置ID: {config.id}\n'
                        f'状态: {"已激活" if config.is_active else "未激活"}\n'
                        f'模板数量: {config.prompt_templates.count()}'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'创建配置失败: {e}')
            )
            raise
    
    def get_generate_template(self):
        """返回生成页面的提示词模板"""
        return """请参考以下信息：

项目通用样式描述：
{{projectStyle}}

全局样式代码参考（**重要：此代码会自动加载到沙盒环境中，你可以直接使用其中定义的 CSS 变量和类**）：
{{globalStyleCode}}

**参考页面代码（可选，如果下方内容为空，请忽略此部分）：**
为了帮助你理解项目当前的风格和上下文，这里提供了用户选择的参考页面的代码。你可以借鉴其中的设计元素或布局思路，但不必严格遵循，请优先满足本次任务的具体要求。

参考页面 HTML:
{{referenceHtml}}

参考页面 CSS:
{{referenceCss}}

参考页面 JavaScript:
{{referenceJs}}

**任务：**
根据下方<具体要求>，创作一段 HTML, CSS, 和 JavaScript 代码。目标是生成一个信息清晰、视觉优雅、交互流畅的**单页演示内容**，它将在特定的 Reveal.js 沙盒环境中展示（详细规则见系统提示）。

**重要:** 你**不需要**在生成的代码中实现任何截图或下载相关的 JavaScript 逻辑。只需确保存在 `id="capture-target"` 的容器即可。

**关键期望：**
 *   **充分利用空间**: 我们的沙盒容器提供了几乎全页的空间，你的设计应该充分利用这个空间，避免过多的留白或空隙。
 *   **内容呈现:** 优先确保核心信息清晰、完整地传达。如果内容超出单页常规容量，请设计合理的滚动或其他交互方式来容纳，避免内容被截断或显得拥挤。
 *   **视觉设计:** 运用简洁、现代的设计原则。注重布局平衡、色彩和谐、字体排版易读性以及适当的留白，创造专业且吸引人的视觉效果。参考项目通用样式描述和全局样式代码，根据内容进行创新。注意文字颜色与背景色的对比度，确保可读性。
 *   **样式实现:** **优先使用 Tailwind CSS 工具类** 来实现样式。仅在 Tailwind 无法满足复杂需求时，才编写自定义 CSS（并确保其作用域）。
 *   **库的引入与使用:** 如果你的代码需要使用 Chart.js, Fabric.js 或 Mermaid 等库，**请确保在 HTML 代码块中包含相应的 `<script>` 或 `<link>` 标签来加载它们**（参考系统提示中的可用路径或使用 CDN），并编写必要的初始化 JavaScript 代码。
 *   **JavaScript 初始化:** 对于需要 JavaScript 初始化的元素（如图表、画布），**必须**提供相应的 JavaScript 代码块，并确保使用 `slideWrapper` 变量来访问 DOM。
 *   **交互体验:** 若涉及交互，应确保其直观、流畅且符合用户预期。
 *   **代码质量:** 生成的代码需结构清晰、语义化，并严格遵守系统提示中描述的沙盒环境约束（特别是 CSS 作用域、JS DOM 操作方式和 Tailwind 的使用）。

**输出格式规范：**
1.  你的回答**必须只包含代码块**，没有任何额外的解释性文字或注释。
2.  必须生成非空的 HTML 代码块。CSS 代码块是可选的（如果样式完全由 Tailwind 实现）。
3.  如果不需要 JavaScript，可以省略 JS 代码块。
4.  使用标准的 Markdown 代码块格式包裹代码，并指定语言（html, css, javascript）。

**【截图目标容器指导】**
为了支持外部截图功能，请确保将主要的可视化内容或需要被截图的核心区域包裹在一个 ID 为 `capture-target` 的 `div` 元素内。
例如:
```html
<div id="capture-target">
  <!-- 这里是你的主要内容，如图表、卡片、文本块等 -->
  <h2>这是标题</h2>
  <img src="/static/images/example.png" alt="示例">
  <p>这是段落。</p>
</div>
```



**<具体要求>**
整体要求：
{{projectDescription}}
内容要求：
{{requirement}}
以上要求，请站在用户的角度理解用户创作内容的表达核心，思考用户想要实现什么样的结果，以最佳设计、表现方式和精确表现用户要求的核心含义。
"""
    
    def get_edit_template(self):
        """返回编辑页面的提示词模板"""
        return """请参考以下背景信息：

项目通用样式描述：
{{projectStyle}}

全局样式代码参考（**重要：此代码会自动加载到沙盒环境中，你可以直接使用其中定义的 CSS 变量和类**）：
{{globalStyleCode}}

项目总体描述（请将其作为核心背景和指导原则）：
{{projectDescription}}

当前HTML代码：
{{currentHtml}}

当前CSS代码：
{{currentCss}}

当前JavaScript代码：
{{currentJs}}

当前 Mermaid 定义（供参考）：
{{currentMermaid}}

参考页面 HTML（可选，可能包含多个页面）：
{{referenceHtml}}

参考页面 CSS（可选，可能包含多个页面）：
{{referenceCss}}

参考页面 JavaScript（可选，可能包含多个页面）：
{{referenceJs}}

**任务：**
根据下方具体要求，修改现有代码。目标是在保持页面核心结构和信息稳定的前提下，实现所需的修改，同时确保最终结果在视觉上依然和谐、功能上符合预期，并能在特定的 Reveal.js 沙盒环境中正确运行（详细规则见系统提示）。

**具体修改要求：**
{{requirement}}

**【截图目标容器指导】**

为了支持外部截图功能，请确保将主要的可视化内容或需要被截图的核心区域包裹在一个 ID 为 `capture-target` 的 `div` 元素内。

例如:
```html
<div id="capture-target">
  <!-- 这里是你的主要内容，如图表、卡片、文本块等 -->
  <h2>这是标题</h2>
  <img src="/static/images/example.png" alt="示例">
  <p>这是段落。</p>
</div>
```

**重要:** 你**不需要**在生成的代码中实现任何截图或下载相关的 JavaScript 逻辑。只需确保存在 `id="capture-target"` 的容器即可。

**执行步骤：**
1. 思考用户想要改什么；
2. 确定要修改哪些代码内容；
3. 检查修改后的代码内容是否符合具体修改要求；
4. 输出**完整**代码块，包括未修改的部分。

**编辑原则与期望：**
*   **全量输出:** 你的回答**必须**包含修改后的**完整** HTML, CSS, 和 JavaScript 代码。即使某部分代码未作修改，也必须完整输出。**严禁**使用"其余保持不变"等省略性描述。
*   **精确修改:** 聚焦于要求中明确提到的修改点，避免对无关部分进行不必要的调整，以维护页面稳定性。
 *   **优雅融入:** 如果要求添加新内容或功能（如图表、交互元素），请将其自然地融入现有布局和设计中，确保视觉协调、功能正常，并考虑内容在单页幻灯片空间内的可访问性（如必要时使用滚动）。**优先使用 Tailwind CSS 实现新增元素的样式**。
 *   **库的引入与使用 (编辑时):** 如果修改或添加的功能需要 Chart.js, Fabric.js 或 Mermaid 等库，**请检查并确保在 HTML 代码块中包含相应的 `<script>` 或 `<link>` 标签来加载它们**，并提供或修改必要的初始化 JavaScript 代码。
 *   **JavaScript 初始化 (编辑时):** 对于需要 JavaScript 初始化的元素（如图表、画布），**必须**确保提供了完整且正确的 JavaScript 代码块，并使用 `slideWrapper` 变量来访问 DOM。
 *   **质量与规范:** 确保所有修改后的代码依然保持高质量（结构清晰、语义化），并严格遵守系统提示中描述的沙盒环境约束（特别是 CSS 作用域、JS DOM 操作方式和 Tailwind 的使用）。

**最终输出格式规范：**
1.  你的回答**必须只包含代码块**，没有任何额外的解释性文字或注释。
2.  必须生成非空的 HTML 代码块。CSS 代码块是可选的（如果样式完全由 Tailwind 实现或未修改）。
3.  如果 JavaScript 未修改或不需要，可以省略 JS 代码块或提供原始 JS 代码。
4.  使用标准的 Markdown 代码块格式包裹代码，并指定语言（html, css, javascript）。
"""
    
    def get_metadata_template(self):
        """返回生成元数据的提示词模板"""
        return """你是一位内容分析专家，专注于分析HTML内容并生成准确的元数据。你的职责是从HTML内容中提取关键信息，生成恰当的标题和摘要。你擅长识别页面的核心主题、结构和功能特点，能够准确地将复杂HTML内容转化为简洁明确的标题和全面精炼的内容摘要。你的分析重点是页面结构、内容语义和交互功能，目标是帮助用户快速理解页面的核心价值。

我需要你按照以下规范生成元数据：

1. 标题生成规范：
   - 突出页面的核心功能或主题
   - 保持简洁性（不超过20字）
   - 使用准确且具有描述性的词语

2. 摘要生成规范：
   - 概括页面的主要内容和功能
   - 突出重要的交互特性
   - 保持精炼（不超过100字）
   - 确保信息的完整性和准确性

3. 内容提取原则：
   - 优先关注语义化标签中的内容
   - 识别重要的标题和关键段落
   - 理解交互组件的功能描述

4. 输出要求：
   - 只生成JSON格式的结果
   - 严格按照规定的字数限制
   - 确保生成的内容准确反映页面本质
   - 使用清晰、专业的语言

基于以下HTML内容生成元数据：

{{html_content}}

请返回JSON格式，包含以下字段：
{
  "title": "页面标题",
  "description": "页面描述"
}"""
    
    def get_style_template(self):
        """返回生成样式的提示词模板"""
        return """你是一位样式设计专家，精通 CSS 设计系统的构建。你的职责是为每个项目建立统一的设计系统，确保视觉语言的一致性和可维护性。

你擅长创建语义化的变量命名、协调一致的颜色系统、优雅的排版结构和灵活的布局规则。你注重响应式设计和可访问性，始终确保样式代码的可复用性和扩展性。

我需要你根据以下项目风格描述，生成一个全局CSS样式代码，包含完整的设计系统变量定义：

{{styleDescription}}

我要求生成的代码必须：

1. 包含:root中的CSS变量定义

2. 颜色系统（只包含以下6个基本颜色）：
   - primary：主要颜色（用于强调和主要操作）
   - secondary：次要颜色（用于次要操作和装饰）
   - text：文本颜色（确保与背景色的对比度）
   - background：背景颜色（考虑内容可读性）
   - accent：强调色（用于重点突出）
   - border：边框颜色（用于分隔和轮廓）

3. 排版系统（使用相对单位 rem，基准为 16px）：
   - font-size-xs：超小字体尺寸（0.75rem）
   - font-size-sm：小字体尺寸（0.875rem）
   - font-size-base：基础字体尺寸（1rem）
   - font-size-lg：大字体尺寸（1.125rem）
   - font-size-xl：超大字体尺寸（1.25rem）
   - font-size-2xl：标题字体尺寸（1.5rem）
   - line-height-tight：紧凑行高（1.2）
   - line-height-normal：标准行高（1.5）
   - line-height-loose：宽松行高（1.8）
   - font-weight-normal：常规字重（400）
   - font-weight-medium：中等字重（500）
   - font-weight-bold：粗体字重（700）

4. 间距系统（使用相对单位 rem）：
   - space-xs：超小间距（0.25rem）
   - space-sm：小间距（0.5rem）
   - space-md：中等间距（1rem）
   - space-lg：大间距（1.5rem）
   - space-xl：超大间距（2rem）

5. 圆角系统（使用相对单位 rem）：
   - radius-sm：小圆角（0.25rem）
   - radius-md：中等圆角（0.5rem）
   - radius-lg：大圆角（1rem）
   - radius-full：完全圆角（9999px）

6. 阴影系统：
   - shadow-sm：小阴影（0 0.0625rem 0.125rem rgba(0,0,0,0.05)）
   - shadow-md：中等阴影（0 0.25rem 0.375rem rgba(0,0,0,0.1)）
   - shadow-lg：大阴影（0 0.625rem 0.9375rem rgba(0,0,0,0.1)）

7. 过渡系统：
   - transition-fast：快速过渡（150ms）
   - transition-normal：标准过渡（300ms）
   - transition-slow：缓慢过渡（500ms）
   - ease-in-out：标准缓动函数

8. 使用现代且协调的配色方案，确保：
   - 颜色之间有足够的对比度
   - 支持浅色和深色主题
   - 颜色具有语义化含义

9. 提供纯CSS代码，不要包含任何解释性文字
"""