# {{ company_name }} · {{ job_title }} · 面试准备全资料

> 生成时间：{{ generated_at }}  ·  报告格式 v{{ report_format_version }}

---

## 一、公司深度画像

### 1.1 基础信息

| 项目 | 内容 | 数据来源 |
|------|------|---------|
| **公司全称** | {{ company_name }} | — |
| **所属行业** | {{ industry }} | {% if report_metadata and report_metadata.data_quality %}{% for q in report_metadata.data_quality if q.field == 'industry' %}{{ q.sources }}{% endfor %}{% endif %} |
| **公司规模** | {{ scale }} | |
| **融资阶段** | {{ funding_stage }} | |
| **成立时间** | {{ established }} | |
| **注册资本** | {{ registered_capital }} | |
| **法定代表人** | {{ legal_person }} | |
| **股权结构** | {{ equity_structure }} | |
| **母公司** | {{ parent_company }} | |
| **所在地** | {{ headquarters }} | |
| **分支机构** | {{ branches }} | |
| **公司简介** | {{ overview }} | |

{% if culture_values %}
### 1.2 公司文化

| 维度 | 内容 |
|------|------|
| **使命** | {{ culture_values.get('mission', '') }} |
| **愿景** | {{ culture_values.get('vision', '') }} |
| **价值观** | {{ culture_values.get('values', '') }} |
| **经营理念** | {{ culture_values.get('operating_philosophy', '') }} |
| **公司文化** | {{ culture }} |

**文化解读（面试可用）：**
{{ culture_values.get('interpretation', culture) }}
{% endif %}

### 1.3 发展历程（关键里程碑）

{% if milestones %}
| 时间 | 里程碑事件 | 来源摘要 |
|------|-----------|---------|
{% for m in milestones %}| {{ m.year }} | {{ m.event }} | {{ m.get('source', '') }} |
{% endfor %}
{% else %}
（暂无发展历程数据）
{% endif %}

### 1.4 近期动态

{% if recent_news %}
{% for news in recent_news %}
- {{ news }}
{% endfor %}
{% else %}
（暂无近期动态数据）
{% endif %}

{% if qualifications %}
### 1.5 资质认证体系

| 资质类型 | 具体内容 |
|---------|---------|
{% for q in qualifications %}| {{ q.type }} | {{ q.name }}（来源：{{ q.source }}） |
{% endfor %}
{% endif %}

---

## 二、产品体系与竞争分析

{% if architecture_overview %}
### 2.0 产品架构总览

> {{ architecture_overview }}
{% endif %}

### 2.1 产品业务线全景

{% if business_lines %}
| 业务线 | 说明 |
|--------|------|
{% for line in business_lines %}| {{ line.name }} | {{ line.description }} |
{% endfor %}
{% else %}
核心产品：{% for p in products %}{{ p }}{% if not loop.last %}、{% endif %}{% endfor %}
{% endif %}

### 2.2 核心产品详解

{% if product_details %}
{% for pd in product_details %}
**{{ pd.name }}**

| 维度 | 内容 |
|------|------|
| **产品定位** | {{ pd.positioning }} |
| **核心功能** | {{ pd.features }} |
| **商业模式** | {{ pd.business_model }} |
| **产品优势** | {{ pd.pros }} |
| **产品劣势** | {{ pd.cons }} |
{% if pd.get('architecture_layer') %}| **架构层次** | {{ pd.architecture_layer }} |{% endif %}
{% if pd.get('source') %}| **数据来源** | {{ pd.source }} |{% endif %}

{% if pd.get('competitors') %}
**产品级竞品对比：**

{% if pd.get('dimensions') %}
| 对比维度 | **{{ pd.name }}** |{% for c in pd.competitors %} **{{ c.name }}** |{% endfor %}
|---------|----------------|{% for c in pd.competitors %}----------------|{% endfor %}
{% set dims = ['产品形态', '技术路线', '目标客群', '商业模式', '核心优势', '核心劣势'] %}
{% for dim in dims %}| **{{ dim }}** | {{ pd.dimensions.get(dim, '') }} |{% for c in pd.competitors %} {{ c.dimensions.get(dim, '') }} |{% endfor %}
{% endfor %}
{% else %}
| 对比维度 |{% for c in pd.competitors %} **{{ c.name }}** |{% endfor %}
|---------|{% for c in pd.competitors %}----------------|{% endfor %}
{% set dims = ['产品形态', '技术路线', '目标客群', '商业模式', '核心优势', '核心劣势'] %}
{% for dim in dims %}| **{{ dim }}** |{% for c in pd.competitors %} {{ c.dimensions.get(dim, '') }} |{% endfor %}
{% endfor %}
{% endif %}

{% endif %}
{% endfor %}
{% else %}
{% if products %}
核心产品：{% for p in products %}{{ p }}{% if not loop.last %}、{% endif %}{% endfor %}
{% else %}
（暂无产品数据）
{% endif %}
{% endif %}

### 2.3 商业模式总结

{% if business_model %}
{{ business_model }}
{% endif %}

{% if revenue_model %}
**盈利模式：** {{ revenue_model }}
{% endif %}

{% if business_model_summary %}
**收入模型：**

| 收入来源 | 模式 | 说明 |
|---------|------|------|
{% for s in business_model_summary %}| {{ s.revenue_source }} | {{ s.model }} | {{ s.description }} |
{% endfor %}
{% endif %}

{% if core_business_logic %}
**核心商业逻辑：** {{ core_business_logic }}
{% endif %}

{% if target_customers %}
**目标客户：** {{ target_customers }}
{% endif %}

### 2.4 竞品分析

{% if competitors %}
| 竞品 | 分析 | 优势 | 劣势 |
|------|------|------|------|
{% for c in competitors %}| **{{ c.name }}** | {{ c.analysis }} | {{ c.advantage }} | {{ c.disadvantage }} |
{% endfor %}
{% else %}
（暂无竞品数据）
{% endif %}

{% if competitive_barriers %}
**竞争壁垒：** {{ competitive_barriers }}
{% endif %}

{% if core_barriers %}
**核心壁垒：**
{% for b in core_barriers %}
- {{ b }}
{% endfor %}
{% endif %}

{% if market_risks %}
**市场风险：** {{ market_risks }}
{% endif %}

{% if core_risks %}
**核心风险：**
{% for r in core_risks %}
- {{ r }}
{% endfor %}
{% endif %}

### 2.5 产品优劣势总结

{% if product_advantages %}
**优势：**
{% for adv in product_advantages %}
- {{ adv }}
{% endfor %}
{% endif %}

{% if product_disadvantages %}
**劣势：**
{% for disadv in product_disadvantages %}
- {{ disadv }}
{% endfor %}
{% endif %}

{% if optimization_suggestions %}
### 2.6 优化建议

| 领域 | 建议 | 预期效果 |
|------|------|----------|
{% for s in optimization_suggestions %}| {{ s.area }} | {{ s.suggestion }} | {{ s.expected_impact }} |
{% endfor %}
{% endif %}

---

## 三、JD 深度对标分析

{% if fit_analysis %}

### 3.1 岗位画像拆解（显性/隐性）

{% if fit_analysis.get("jd_deconstruction") %}
| JD显性要求 | 隐性考察点 | 你的背景对照 |
|-----------|-----------|-------------|
{% for row in fit_analysis.get("jd_deconstruction", []) %}| {{ row.explicit_requirement }} | {{ row.hidden_examination }} | ✅ {{ row.candidate_match }} |
{% endfor %}
{% endif %}

### 3.2 JD 要求 vs 个人能力对照

{% if fit_analysis.get("jd_requirement_vs_candidate") %}
| JD 要求 | 候选人匹配情况 | 评分 | 说明 |
|---------|---------------|:----:|------|
{% for row in fit_analysis.get("jd_requirement_vs_candidate", []) %}| {{ row.requirement }} | {{ row.candidate_match }} | {{ row.score }}/10 | {{ row.note }} |
{% endfor %}
{% else %}
（无具体 JD 对照数据）
{% endif %}

### 3.3 核心契合点

{% if fit_analysis.get("core_fit_points") %}
{% for point in fit_analysis.get("core_fit_points", []) %}
- **{{ point.point }}**：{{ point.detail }}
{% if point.get("interview_script") %}
  - **面试话术：** {{ point.interview_script }}
{% endif %}
{% endfor %}
{% else %}
（暂无数据）
{% endif %}

### 3.4 需要补强的点

{% if fit_analysis.get("gap_analysis") %}
| 补强方面 | 严重程度 | 应对策略 |
|---------|:--------:|----------|
{% for gap in fit_analysis.get("gap_analysis", []) %}| {{ gap.gap }} | {{ gap.severity }} | {{ gap.strategy }} |
{% endfor %}
{% else %}
（暂无数据）
{% endif %}

### 3.5 契合度总评

**综合评分：** {% if fit_analysis.get("overall_fit_score") %}{{ fit_analysis.get("overall_fit_score") }}/10{% else %}-{% endif %}

{{ fit_analysis.get("summary", "") }}

{% else %}
（个人契合度分析需要候选人知识库数据，当前未加载）
{% endif %}

---

## 四、面试策略与应答话术

{% if self_intro_2min %}
### 4.1 自我介绍（2分钟版）

> {{ self_intro_2min }}
{% endif %}

### 4.2 高频问题与话术

{% if questions %}
{% set categories = {
  "自我介绍与动机": [],
  "专业能力": [],
  "行业认知": [],
  "情境应对": []
} %}

{% for q in questions %}
  {% set cat = q.get("category", "专业能力") %}
  {% if cat in categories %}
    {% set _ = categories[cat].append(q) %}
  {% else %}
    {% set _ = categories["专业能力"].append(q) %}
  {% endif %}
{% endfor %}

{% for cat_name, cat_questions in categories.items() if cat_questions %}

#### {{ loop.index }}. {{ cat_name }}

{% for q_item in cat_questions %}
**问题 {{ loop.index }}：{{ q_item.q }}**

<details>
<summary>查看回答思路</summary>

{{ q_item.a }}

{% if q_item.get("answer_script") %}
**话术参考：**
{{ q_item.answer_script }}
{% endif %}

</details>

<br/>
{% endfor %}
{% endfor %}

{% else %}
（暂无面试问题数据）
{% endif %}

### 4.3 反问面试官

{% if ask_questions %}
{% for aq in ask_questions %}
1. {{ aq }}
{% endfor %}
{% else %}
（暂无数据）
{% endif %}

{% if tips %}
### 4.4 面试建议

{{ tips }}
{% endif %}

{% if narrative_angle %}
### 4.5 叙事角度建议

{{ narrative_angle }}
{% endif %}

---

## 数据来源说明

> 数据来源声明：本文除候选人的个人背景信息外，所有公司/产品/行业/竞品数据均通过 SearXNG 搜索引擎（360search + Baidu + chinaso + sogou_wechat）检索公开信息获取，每项数据均标注来源与可信度分级（A=官方/一手 · B=百科 · C=工商登记 · D=新闻 · E=商业目录 · F=用户生成 · G=单源/未验证）。

| 项目 | 内容 |
|------|------|
| **搜索引擎** | {{ report_metadata.search_engines_used | join(', ') if report_metadata else 'SearXNG' }} |
| **搜索查询次数** | {{ report_metadata.total_search_queries if report_metadata else '-' }} |
| **累计搜索结果** | {{ report_metadata.total_results_collected if report_metadata else '-' }} |
| **搜索性能 P50** | {{ report_metadata.search_performance.p50_ms if report_metadata else '-' }}ms |
| **搜索性能 P95** | {{ report_metadata.search_performance.p95_ms if report_metadata else '-' }}ms |
| **数据来源分级** | A=官方/一手 · B=百科 · C=工商登记 · D=新闻 · E=商业目录 · F=用户生成 · G=单源/未验证 |

{% if report_metadata and report_metadata.data_quality %}
**数据质量标记：**
{% for q in report_metadata.data_quality %}
- {{ q.field }}：{{ q.status }}（{{ q.sources }}）
{% endfor %}
{% endif %}

{% if report_metadata and report_metadata.unverifiable_claims_removed %}
**已过滤的AI推测：**
{% for claim in report_metadata.unverifiable_claims_removed %}
- ⚠️ {{ claim }}
{% endfor %}
{% endif %}

---

<footer>
  <small>由 AI 面试助手自动生成 · {{ generated_at }} · 仅供参考，请结合实际情况使用</small>
</footer>
