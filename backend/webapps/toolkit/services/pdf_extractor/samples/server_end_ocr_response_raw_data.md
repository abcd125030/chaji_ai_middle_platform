<|ref|>title<|/ref|><|det|>[[115, 83, 845, 130]]<|/det|>
# Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models  

<|ref|>text<|/ref|><|det|>[[123, 152, 829, 205]]<|/det|>
Qizheng Zhang \(^{1*}\) Changran Hu \(^{2*}\) Shubhangi Upasani \(^{2}\) Boyuan Ma \(^{2}\) Fenglu Hong \(^{2}\) Vamsidhar Kamanuru \(^{2}\) Jay Raint \(^{2}\) Chen Wu \(^{2}\) Mengmeng Ji \(^{2}\) Hanchen Li \(^{3}\) Urmish Thakker \(^{2}\) James Zou \(^{1}\) Kunle Olukotun \(^{1}\)  

<|ref|>text<|/ref|><|det|>[[123, 210, 785, 228]]<|/det|>
\(^{1}\) Stanford University \(^{2}\) SambhaNova Systems, Inc. \(^{3}\) UC Berkeley \(^{*}\) equal contribution  

<|ref|>text<|/ref|><|det|>[[123, 232, 600, 247]]<|/det|>
\(\boxed{ \begin{array}{r l} \end{array} }\) qizhengz@stanford.edu, changran.hu@sambanovasystems.com  

<|ref|>sub_title<|/ref|><|det|>[[460, 283, 537, 301]]<|/det|>
## Abstract  

<|ref|>text<|/ref|><|det|>[[114, 311, 884, 558]]<|/det|>
Large language model (LLM) applications such as agents and domain- specific reasoning increasingly rely on context adaptation—modifying inputs with instructions, strategies, or evidence, rather than weight updates. Prior approaches improve usability but often suffer from brevity bias, which drops domain insights for concise summaries, and from context collapse, where iterative rewriting erodes details over time. Building on the adaptive memory introduced by Dynamic Cheatsheet, we introduce ACE (Agentic Context Engineering), a framework that treats contexts as evolving playbooks that accumulate, refine, and organize strategies through a modular process of generation, reflection, and curation. ACE prevents collapse with structured, incremental updates that preserve detailed knowledge and scale with long- context models. Across agent and domain- specific benchmarks, ACE optimizes contexts both offline (e.g., system prompts) and online (e.g., agent memory), consistently outperforming strong baselines: \(+10.6\%\) on agents and \(+8.6\%\) on finance, while significantly reducing adaptation latency and rollout cost. Notably, ACE could adapt effectively without labeled supervision and instead by leveraging natural execution feedback. On the AppWorld leaderboard, ACE matches the top- ranked production- level agent on the overall average and surpasses it on the harder test- challenge split, despite using a smaller open- source model. These results show that comprehensive, evolving contexts enable scalable, efficient, and self- improving LLM systems with low overhead.  

<|ref|>sub_title<|/ref|><|det|>[[115, 581, 259, 599]]<|/det|>
## 1 Introduction  

<|ref|>image<|/ref|><|det|>[[131, 620, 863, 840]]<|/det|>
<|ref|>image_caption<|/ref|><|det|>[[115, 853, 883, 887]]<|/det|>
<center>Figure 1: Overall Performance Results. Our proposed framework, ACE, consistently outperforms strong baselines across agent and domain-specific reasoning tasks. </center>  

<|ref|>text<|/ref|><|det|>[[115, 908, 883, 942]]<|/det|>
Modern AI applications based on large language models (LLMs), such as LLM agents [49, 52] and compound AI systems [55], increasingly depend on context adaptation. Instead of modifying model weights, context