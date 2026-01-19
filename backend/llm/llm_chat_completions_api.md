接口 1：获取 token

## 接口描述
此接口用于获取用户认证所需的 token。在使用需要身份验证的舆情分析系统接口前，用户需要先通过该接口获取有效的 token。

## 请求URL
http://139.224.106.161:8015/api/service/auth/

## 请求方式
POST

## 请求示例
```bash
curl --location 'http://139.224.106.161:8015/api/service/auth/' \
--header 'Content-Type: application/json' \
--data '{
  "appid": "your_appid_here",
  "secret": "your_secret_here"
}'
```
## 返回结果

{
    "access_token": "your_access_token_here",
    "refresh_token": "your_refresh_token_here",
    "expires_in": 1800
}

接口 2 调用大模型

## 接口描述
此接口用于与大型语言模型(LLM)进行交互，获取聊天式补全结果。该接口支持流式和非流式响应，适用于需要AI生成文本的各种场景。

## 请求URL
`http://139.224.106.161:8015/api/llm/v1/chat/completions/`

## 请求方式
POST

## 请求头
- `Content-Type`: application/json
- `Authorization`: Bearer {access_token} (必填，http://139.224.106.161:8015/api/service/auth/的结果)

## 请求参数
请求体为JSON格式，结构如下：
```json
{
    "model": "模型名称",
    "messages": [
        {
            "role": "user|assistant|system",
            "content": "消息内容"
        }
    ],
    "stream": true|false,
    "max_tokens": 最大token数,
    "temperature": 0.7,
    "top_p": 0.7,
    "frequency_penalty": 0.5,
    "n": 1,
    "session_id": "会话ID"
}

参数说明：

- model : 指定使用的LLM模型(如qwq-32b, deepseek-r1等)
- messages : 对话消息数组，包含角色(role)和内容(content)
- stream : 是否启用流式响应 (qwq-32必须是流式响应，deepseek-r1可以是流式响应，也可以不是流式响应)
- max_tokens : 生成的最大token数量(8096)
- temperature : 控制生成随机性的参数(0-1)
- top_p : 核采样参数(0-1)
- frequency_penalty : 频率惩罚参数(0-1)
- n : 返回结果数量
- session_id : 可选会话ID，用于跟踪对话


## 响应示例
成功响应(非流式):
{
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "生成的回复内容"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 提示token数,
        "total_tokens": 总token数,
        "completion_tokens": 生成token数
    },
    "session_id": "会话ID",
    "model_name": "模型显示名称",
    "origin": {
        "model": "原始模型名称",
        "messages": [
            {
                "role": "user",
                "content": "原始用户消息"
            }
        ],
        "stream": true|false,
        "max_tokens": 最大token数,
        "temperature": 0.7,
        "top_p": 0.7,
        "frequency_penalty": 0.5,
        "n": 1
    }
}


### 请求示例1

curl --location 'http://139.224.106.161:8015/api/llm/v1/chat/completions/' \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwq-32b",
    "messages": [
        {
            "role": "user",
            "content": "简单介绍一下霸王茶姬"
        }
    ],
    "stream": false,
    "max_tokens": 8096,
    "temperature": 0.7,
    "top_p": 0.7,
    "frequency_penalty": 0.5,
    "n": 1,
    "session_id": "0fb64acf-990b-4099-b5fe-334061a5b55b"
}'

### 请求示例1返回内容
{
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "**霸王茶姬**是中国近年来崛起的知名新茶饮品牌，以“水果茶”为核心产品，主打高性价比与国潮文化，深受年轻消费者喜爱。以下是其核心信息：\n\n### 1. **品牌背景**\n- **成立时间**：2017年，总部位于云南昆明。\n- **定位**：定位为“国民水果茶品牌”，主打“鲜果+中国茶”的组合，价格亲民（通常在15-25元），介于高端品牌（如喜茶）与低价品牌（如蜜雪冰城）之间。\n\n### 2. **产品特色**\n- **核心产品**：以“霸气系列”水果茶闻名，如**霸气芝士莓莓**、**霸气葡萄玉麒麟**、**霸气芒果**等，强调鲜果现切、茶底选用云南优质茶叶。\n- **多元化产品线**：除水果茶外，还推出奶茶、纯茶、季节限定款（如冬季热饮）及周边商品。\n\n### 3. **门店与市场**\n- **门店规模**：截至2023年，门店数量已突破**4000家**，覆盖中国200多个城市，并拓展至东南亚市场（如新加坡、马来西亚）。\n- **扩张策略**：以“轻资产”模式快速扩张，注重下沉市场渗透，同时在一线城市核心商圈布局。\n\n### 4. **品牌文化与创新**\n- **国潮元素**：包装设计、门店装修融入中国传统文化符号（如水墨风、国风插画），契合年轻人对“国潮”的追捧。\n- **社会责任**：发起“茶姬助学计划”，资助偏远地区教育；推行环保包装，使用可降解材料减少塑料污染。\n- **营销亮点**：通过社交媒体（抖音、小红书）打造爆款话题，与热门IP联名（如《黑神话：悟空》），强化品牌年轻化形象。\n\n### 5. **市场地位**\n- 作为新茶饮赛道的“黑马”，凭借差异化定位和高效运营，迅速跻身行业头部品牌，与喜茶、奈雪的茶形成竞争，同时吸引资本关注（曾获融资）。\n\n### 总结\n霸王茶姬以“鲜果茶”为核心，结合国潮文化与亲民价格，成功在竞争激烈的茶饮市场中占据一席之地，成为年轻人日常消费的热门选择。其快速扩张与品牌创新，使其成为观察中国新消费趋势的重要案例。"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 15,
        "total_tokens": 939,
        "completion_tokens": 924
    },
    "session_id": "0fb64acf-990b-4099-b5fe-334061a5b55b",
    "model_name": "阿里百炼qwq-32b",
    "origin": {
        "model": "qwq-32b",
        "messages": [
            {
                "role": "user",
                "content": "简单介绍一下霸王茶姬"
            }
        ],
        "stream": true,
        "max_tokens": 8096,
        "temperature": 0.7,
        "top_p": 0.7,
        "frequency_penalty": 0.5,
        "n": 1
    }
}


### 请求示例2
curl --location 'http://139.224.106.161:8015/api/llm/v1/chat/completions/' \
--header 'Content-Type: application/json' \
--data '{
	"model": "deepseek-r1",
	"messages": [
		{
			"role": "user",
			"content": "简单介绍一下华贸中心"
		}
	],
	"stream": false,
	"max_tokens": 8096,
	"temperature": 0.7,
	"top_p": 0.7,
	"frequency_penalty": 0.5,
	"n": 1,
    "session_id": "cf8129fa-72b8-40f5-b229-70a7e3bac352"
}'

### 请求示例2返回内容
{
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "华贸中心是位于中国北京朝阳区的大型城市综合体，由国华置业开发，2007年建成。其核心特点如下：\n\n**1. 多元业态组合**\n- 3栋超甲级写字楼：吸引微软、特斯拉等500强企业\n- 华贸购物中心+北京SKP：SKP连续多年蝉联全球店王，2020年销售额达177亿元\n- 奢华酒店双星：丽思卡尔顿（客房306间）与JW万豪（客房588间）\n- 高端公寓：2栋服务式公寓楼\n\n**2. 设计亮点**\n- 美国KPF建筑师事务所主创设计\n- 15万㎡中央公园景观\n- 连廊系统串联各功能区\n\n**3. 经济影响力**\n- 日均客流量10万人次\n- 年税收贡献超40亿元\n- 带动大望路商圈升级为国际商务区\n\n**4. 扩展布局**\n- 已进驻上海、南京等城市\n- 上海华贸中心（北外滩）规划总建面45万㎡\n\n该项目通过\"高端商业+顶级商务\"模式，重新定义了北京CBD的商务生态，成为城市更新的标杆案例。2021年入选北京市首批\"智慧商圈\"示范项目。"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 8,
        "total_tokens": 627,
        "completion_tokens": 619
    },
    "session_id": "cf8129fa-72b8-40f5-b229-70a7e3bac352",
    "model_name": "阿里百炼DeepSeek-R1",
    "origin": {
        "model": "deepseek-r1",
        "messages": [
            {
                "role": "user",
                "content": "简单介绍一下华贸中心"
            }
        ],
        "stream": false,
        "max_tokens": 8096,
        "temperature": 0.7,
        "top_p": 0.7,
        "frequency_penalty": 0.5,
        "n": 1
    }
}


