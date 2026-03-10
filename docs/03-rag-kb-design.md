# 知识库分片、向量化、BM25 设计与版本管理策略

## 1. 知识库四层结构与语料角色

### 1.1 层级图

```
L0  基础规范层
    └── 行业标准、国标、IEC 规范（不直接摄入，作为 L1/L2 编写依据）

L1  总览路由层
    ├── L1.ROUTER.001    — 症状 → 诊断路径路由表
    └── L1.OVERVIEW.001  — 水电机组结构与运行原理总览

L2  专题知识层
    ├── L2.TOPIC.VIB.001  — 振动/摆度专题诊断指南
    ├── L2.TOPIC.GOV.001  — 调速器/油压专题诊断指南
    ├── L2.TOPIC.BEAR.001 — 轴承温度专题诊断指南
    ├── L2.SUPPORT.RULE.001 — 硬阈值与操作红线规则库
    └── L2.SUPPORT.CASE.001 — 行业典型故障案例库

L3  厂站专有层（待接入）
    ├── 01_机组台账       — 设备参数、检修历史
    ├── 03_保护定值       — 本厂专项保护整定值
    └── 05_历次缺陷       — 本厂历次缺陷记录
```

### 1.2 各层在 RAG 中的召回权重

| 层级 | Corpus | 召回权重说明 |
|------|--------|-------------|
| L1 | procedure | 提供背景知识，召回频率高但内容通用 |
| L2.TOPIC.* | procedure | 核心专题知识，与故障类型强相关 |
| L2.SUPPORT.RULE | rule | 独立 collection，硬阈值判断专用 |
| L2.SUPPORT.CASE | case | 独立 collection，案例相似度匹配 |
| L3（待接入） | plant_<id>_* | 本厂专有，优先级最高 |

### 1.3 YAML 前置元数据设计

每个知识库文档以 YAML frontmatter 开头：

```yaml
---
doc_id: L2.TOPIC.VIB.001
title: 水电机组振动摆度诊断专题指南
version: 1.0.0
route_keys: [振动, 摆度, 轴振, 瓦振]
upstream: [L1.ROUTER.001]
downstream: [L2.SUPPORT.RULE.001, L2.SUPPORT.CASE.001]
---
```

字段说明：
- `doc_id`：全局唯一标识符，用于 corpus 过滤和 sources 追踪
- `route_keys`：与 `TOPIC_KEYWORDS` 对应，用于检索路由
- `upstream`：该文档的上游依赖（总览/路由文档）
- `downstream`：该文档的下游扩展（规则/案例文档）

---

## 2. 渐进式披露分片策略（Progressive Disclosure Chunking）

### 2.1 什么是渐进式披露

渐进式披露（Progressive Disclosure）是指按信息重要性层次控制 context 填充：用户首先获得高层摘要（L1），按需深入专题细节（L2 TOPIC），最后获取支撑证据（L2 RULE/CASE）。

在 RAG 场景中，这意味着：
- reasoning 节点的 prompt 先填入 L1 总览（背景框架）
- 再填入 L2 专题（核心知识）
- 最后填入规则库和案例库（验证证据）
- 总 context 长度控制在模型上下文窗口的 30-40% 以内

### 2.2 两阶段分块策略

实现文件：`backend/app/rag/chunker.py`

**第一阶段：`MarkdownHeaderTextSplitter`**

```python
_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]
header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=_HEADERS,
    strip_headers=False,  # 保留标题，使 chunk 具备自解释性
)
```

按 Markdown 标题切分，每个 heading section 成为独立 chunk。标题保留在 chunk 内容中，使嵌入向量包含章节语义。

**第二阶段：`RecursiveCharacterTextSplitter`（fallback）**

```python
_FALLBACK_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=["\n\n", "\n", "。", "；", " ", ""],
)
```

对 heading chunk 仍超过 600 字符的部分进一步切分。

### 2.3 Chunk size=600 / overlap=80 的选择依据

| 参数 | 值 | 依据 |
|------|-----|------|
| chunk_size | 600 | BGE-large-zh 嵌入上下文窗口 512 tokens，600 中文字符约 400-450 tokens，留余量 |
| chunk_overlap | 80 | 约 chunk_size 的 13%，覆盖跨 chunk 边界的句子断裂；过大会增加存储和检索噪声 |

600 字符的设计依据：
- 水电运维知识段落平均长度约 200-400 字
- chunk 太小（< 200）：语义碎片化，embedding 质量下降
- chunk 太大（> 800）：超出 BGE 上下文窗口，尾部内容嵌入质量降低

### 2.4 中文标点符号分隔符设计

`separators=["\n\n", "\n", "。", "；", " ", ""]`

分隔符优先级从高到低：
1. `\n\n`：段落边界（最优切分点）
2. `\n`：行边界
3. `。`：中文句子结束（保证句子完整性）
4. `；`：分号，适用于条目式规程
5. ` `：空格（fallback，英文单词边界）
6. `""`：字符级切分（最后手段）

不使用英文 `.` 作为分隔符，避免将数字小数点（如 `0.85`）误切。

### 2.5 元数据继承策略

```python
# chunker.py:43-45
merged_meta = {**doc.metadata, **sc.metadata}
chunks.append(Document(page_content=sc.page_content, metadata=merged_meta))
```

父文档 metadata（`doc_id`, `title`, `version`, `route_keys`）合并到每个 chunk 的 metadata 中，子 chunk 的 metadata 优先（`**sc.metadata` 在右侧覆盖父级同名字段）。

这确保每个 chunk 携带完整的溯源信息，`sources` 字段可从任意 chunk 的 `doc_id` 追溯到原始文档。

---

## 3. 向量化设计

### 3.1 BAAI/bge-large-zh-v1.5 选型依据

| 模型 | 维度 | 中文专业术语质量 | 本地部署 | 成本 |
|------|------|----------------|----------|------|
| BAAI/bge-large-zh-v1.5 | 1024 | 优秀（MTEB 中文榜 Top 3） | 是 | 无 API 成本 |
| text-embedding-3-large | 3072 | 良好 | 否（API） | $0.13/MTok |
| m3e-base | 768 | 中等（通用中文） | 是 | 无 |
| BAAI/bge-m3 | 1024 | 优秀（多语言） | 是 | 无 |

水电运维术语（如"导叶反馈信号不一致"、"压油罐补气阀"）属于低频专业词汇，需要在 MTEB 中文语义相似度任务上表现优秀的模型。bge-large-zh-v1.5 在此类任务上优于通用模型。

### 3.2 1024-dim cosine similarity 的性能影响

1024 维向量的 cosine 相似度计算（FAISS/Qdrant）：
- 单次查询延迟（10K 向量）：< 5ms（CPU），< 1ms（GPU）
- 存储：每个 chunk 1024 × 4 bytes = 4KB，10K chunks ≈ 40MB（可接受）
- 与 768 维相比：质量提升约 5-8%，存储/计算成本增加约 33%

### 3.3 三独立 Collection 设计

| Collection | doc_ids | 用途 |
|------------|---------|------|
| `hydro_kb_procedure` | L2.TOPIC.* + L1.* | 诊断流程和背景知识 |
| `hydro_kb_rule` | L2.SUPPORT.RULE.001 | 硬阈值和操作红线 |
| `hydro_kb_case` | L2.SUPPORT.CASE.001 | 历史相似案例 |

Collection 隔离的好处：
- **语义隔离**：规则库的强断言语言（"必须"、"严禁"）不会污染案例库的叙述性语言的语义空间
- **过滤效率**：检索时直接指定 collection，无需 metadata 后过滤
- **独立更新**：规则库更新不触发 procedure/case collection 重建

---

## 4. BM25 设计

### 4.1 jieba 分词在水电专业术语上的行为

jieba 默认词典对通用中文分词效果好，但水电专业术语可能被错误切分：

| 原词 | jieba 默认切分 | 期望切分 |
|------|--------------|---------|
| 导叶开度 | 导叶 / 开度 | 导叶开度（应保持整体） |
| 压油罐 | 压 / 油罐 | 压油罐 |
| 主配压阀 | 主 / 配压阀 | 主配压阀 |
| 调速器 | 调速 / 器 | 调速器 |

由于 jieba 会将"导叶"和"开度"分开，BM25 层面的精确匹配依赖于 tokenized query 和 tokenized document 的重叠，通用词典下仍能覆盖大多数场景。

### 4.2 自定义专业词典接入路径

```python
# 在 bm25_index.py 初始化时加载专业词典
import jieba
jieba.load_userdict("./knowledge_base/hydro_dict.txt")
```

`hydro_dict.txt` 格式（每行：词语 频率 词性）：
```
压油罐 10 n
主配压阀 10 n
导叶开度 10 n
推力轴承 10 n
```

接入后，上述专业术语在分词时保持整体，BM25 召回精度提升（P2 优化项）。

### 4.3 BM25Okapi 参数说明

`BM25Okapi` 使用 `rank_bm25` 库（`backend/app/rag/bm25_index.py:23`），默认参数：

- `k1 = 1.5`：词频饱和因子。高 k1 使词频增加带来的分数提升更平滑，适合长文档（水电规程文档通常 500-2000 字）
- `b = 0.75`：文档长度归一化因子。b=0.75 在不归一化（b=0）和完全归一化（b=1）之间取中，适合长度差异大的混合语料（L1 总览文档 vs. L2 专题细节）

### 4.4 Pickle 持久化策略与增量更新限制

```python
# BM25Index.save / load
def save(self, path: str | Path) -> None:
    with open(path, "wb") as f:
        pickle.dump(self, f)
```

文件路径：`./knowledge_base/vector_store/bm25_<corpus>.pkl`

**限制**：BM25Okapi 的 IDF 值在构建时基于整个语料库计算，不支持增量更新。添加新文档必须重建整个索引（`ingest_kb.py --reset`）。

**影响**：当前 KB 文档量较小（< 100 文档），重建耗时 < 10s，可接受。文档量 > 1000 时需考虑分批重建策略。

---

## 5. 混合检索 RRF 融合

### 5.1 Reciprocal Rank Fusion 公式

$$\text{RRF\_score}(d) = \sum_{r \in R} \frac{1}{k + \text{rank}_r(d)}$$

其中：
- $R$：所有参与融合的排序列表（BM25 结果列表 + Dense 结果列表）
- $k = 60$：平滑常数
- $\text{rank}_r(d)$：文档 $d$ 在排序列表 $r$ 中的排名（从 0 开始）

实现参考：`backend/app/rag/hybrid_retriever.py:21-36`

### 5.2 为何 k=60

`k=60` 是 RRF 的经典默认值（Cormack et al., 2009），对头部结果的平滑效果：

| rank | k=0, score | k=60, score | 差异 |
|------|-----------|------------|------|
| 0（第1名） | 1.000 | 0.0164 | 平滑后头部优势减小 |
| 1（第2名） | 0.500 | 0.0161 | 头部间差异缩小 |
| 10（第11名） | 0.091 | 0.0141 | 中部文档获得合理分数 |
| 59（第60名） | 0.017 | 0.0083 | 尾部依然有贡献 |

k=60 防止单一排序列表中的第1名对最终结果产生过度主导，使 BM25 和 Dense 两种信号能平衡融合。

### 5.3 BM25 与 Dense 权重对等

当前实现中 BM25 结果列表和 Dense 结果列表在 RRF 中权重相等（均传入 `lists` 数组一次）。

不预设偏向的理由：
- 水电运维查询中，术语精确匹配（BM25 优势）和语义相似度（Dense 优势）同等重要
- 具体偏向应基于实际召回评估数据调整，而非预设（见第 7 节评估体系）

如需调整权重，可通过重复传入某个列表实现（如传入 Dense 列表两次相当于 2:1 权重）。

### 5.4 Reranker 降级路径

```python
# hybrid_retriever.py:74-85
def _rerank(query: str, docs: list[Document]) -> list[Document]:
    try:
        from FlagEmbedding import FlagReranker
        reranker = FlagReranker(settings.reranker_model, use_fp16=True)
        pairs = [[query, d.page_content] for d in docs]
        scores = reranker.compute_score(pairs)
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        return [d for _, d in ranked]
    except Exception:
        return docs  # 降级：返回 RRF 融合结果
```

`FlagEmbedding` 库未安装时（或 GPU 内存不足时），`except Exception` 捕获所有异常，直接返回 RRF 融合结果。这确保检索功能不因 reranker 缺失而中断，只是召回质量略有下降。

---

## 6. 知识库版本管理策略（未来）

### 6.1 语义化版本规范

```
KB 版本格式：v{major}.{minor}.{patch}

v1.0.0 = L0 + L1 + L2（基础版）
v1.1.0 = v1.0.0 + L3_plant_yantan（接入滩坝电站 L3）
v1.2.0 = v1.1.0 + L3_plant_longtan（接入龙滩电站 L3）
v2.0.0 = 新增故障类型（如发电机励磁异常）
```

### 6.2 向量库版本化方案

Collection 命名加 version suffix：
```
hydro_kb_procedure_v1
hydro_kb_procedure_v2  ← 新版本迁移完成前新旧并存
```

迁移策略：新版本 collection 建立后，通过 `config.py` 切换指向，旧 collection 保留 7 天后删除。

### 6.3 BM25 与 Vector Store 的同步一致性

`ingest_kb.py` 保证两者在同一次运行中原子更新：

```
ingest_kb.py --reset
    ├── 1. 清空 Chroma collection（或指定的 Qdrant collection）
    ├── 2. 重新摄入所有文档（chunk → embed → upsert）
    └── 3. 重建 BM25 index → 保存 pkl 文件
```

`--reset` 标志防止向量库和 BM25 索引出现版本不一致（如只更新了向量库但未重建 BM25）。

### 6.4 增量摄入策略（P2）

基于 content hash 的增量更新：
1. 摄入时计算每个文档的 `sha256(content)`，存储到 metadata
2. 再次摄入时对比 hash，仅重新处理变更文档
3. BM25 index 仍需全量重建（受 BM25Okapi IDF 计算限制）

### 6.5 多电厂命名空间隔离

Collection 命名规范：`plant_<plant_id>_<corpus>`

```
plant_yantan_procedure
plant_yantan_rule
plant_yantan_case
plant_longtan_procedure
...
```

BM25 index 文件：`bm25_plant_<plant_id>_<corpus>.pkl`

查询时通过请求中的 `plant_id` 参数路由到对应 collection（`retrieval.py` 中 `get_retriever(corpus)` 接受 `plant_id` 参数扩展）。

---

## 7. 质量评估体系（scripts/eval_retrieval.py 占位）

### 7.1 评估指标

| 指标 | 说明 | 目标值（预估） |
|------|------|---------------|
| Top-5 Recall | 相关文档出现在前 5 名的比例 | > 0.85 |
| MRR | Mean Reciprocal Rank，第一个相关文档的倒数排名均值 | > 0.75 |
| NDCG@10 | Normalized Discounted Cumulative Gain，考虑相关性等级 | > 0.80 |

### 7.2 黄金标准测试集构建建议

建议构建 3 个故障场景 × 5 个查询变体 = 15 个测试用例：

| 场景 | 查询变体示例 | 期望召回文档 |
|------|------------|-------------|
| 振动摆度异常 | "1号机组摆度偏大"、"轴振超标" | L2.TOPIC.VIB.001, L2.SUPPORT.RULE.001 |
| 调速器油压低 | "压油罐压力不足"、"导叶无法开启" | L2.TOPIC.GOV.001, L2.SUPPORT.RULE.001 |
| 推力轴承温升 | "推力轴承温度高"、"冷却水流量不足" | L2.TOPIC.BEAR.001, L2.SUPPORT.CASE.001 |

### 7.3 评估执行方式（占位）

```bash
# 待实现
python scripts/eval_retrieval.py \
  --test-set knowledge_base/eval/golden_set.jsonl \
  --corpus procedure rule case \
  --metrics recall mrr ndcg
```
