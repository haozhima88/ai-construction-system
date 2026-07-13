# 企业定额协同审核工作台原型

这是 `construction_cost_knowledge_engine` 的 Web 协同审核原型，用于浏览清单-定额候选映射、查看省定额与企业候选价对比，并试填企业价草稿。

## 本轮稳定化修复

- 已修复企业价字段别名读取，支持 `enterprise_*_fee_candidate`、`human_selected_*`、`ai_recommended_*`、`raw_*`、`internal_*` 等字段。
- 已修复省定额人材机管合计读取，支持 `raw_labor_fee`、`raw_material_fee`、`raw_machine_fee`、`raw_management_fee`、`raw_total_fee`。
- 已修复“采用省定额价”：会同时写入人工费、材料费、机具费、管理费、合计；四项缺失但合计存在时会设置人工覆盖并提示人工确认。
- 已修复树形展开状态：展开节点保存到 localStorage，选择清单后自动展开父级节点。
- 已增加左右面板宽度拖拽，左侧最小 240px，右侧最小 280px，中间表格最小 600px。
- 已增加 dirty state、切换清单前提示、浏览器刷新/关闭前提示。
- 已增加 localStorage 临时草稿缓存。
- 已增加 2 秒 debounce 自动保存和 30 秒周期自动保存。
- 已增加保存失败重试。
- 已增加草稿快照导出和 audit_log 快照导出。

## 治理边界

- 不修改清单基线、定额基线、映射候选或企业价格源文件。
- 草稿只写入本目录 SQLite 的 `web_price_review_draft` 表。
- 每次保存、清空和快照导出都会写入或保留 `web_audit_log`。
- 不生成 `approved`，不生成正式企业定额，不写生产数据库。
- 当前仍不是正式生产系统，没有复杂权限、审批流或多人冲突控制。

## 启动

```powershell
cd E:\workspace\01_Projects\ai-construction-system\construction_cost_knowledge_engine
python web_collab_prototype\build_view_model.py
python -m uvicorn web_collab_prototype.app:app --host 127.0.0.1 --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/
```

## 草稿保存

1. 左侧按“附录 / 章节 / 清单项”展开目录。
1. 点击清单项后，中间表格显示候选定额、省定额价格、企业候选价、差异率和治理风险。
1. 点击“编辑企业价”填写企业人工费、材料费、机具费、管理费和备注。
1. 企业合计默认自动计算；勾选“人工覆盖合计”后可以手动填合计。
1. 点击“采用省定额价”会把省定额价格复制为企业价草稿。
1. 保存成功后，草稿版本号 `draft_version` 自动递增。

## 自动保存和本地缓存

- 字段变化后会写入 `localStorage`：
  `web_collab_draft_cache::{bill_code_9}::{quota_source_code}`
- 编辑框再次打开时，如果发现本地未保存草稿，会提示是否恢复。
- 保存成功后会清除对应 localStorage 缓存。
- 自动保存使用 `selected_price_source=autosave_enterprise_draft` 和 `save_status=autosaved`。
- 如果保存失败，页面保留 localStorage 缓存并显示“重试保存”按钮。

## 快照导出

- 草稿快照：
  `GET /api/draft/export_snapshot`
- audit_log 快照：
  `GET /api/audit/export_snapshot`
- 快照文件输出到：
  `construction_cost_knowledge_engine/data/private/reference_extraction/runs/WEB_COLLAB_PROTOTYPE_STABILIZATION_1/exports/`

## API

- `GET /api/tree/hierarchy`
- `GET /api/bill/{bill_code_9}/rows`
- `GET /api/quota/{quota_source_code}/price`
- `GET /api/draft/{bill_code_9}/{quota_source_code}`
- `POST /api/draft/save`
- `POST /api/draft/clear`
- `GET /api/draft/export_snapshot`
- `GET /api/audit/export_snapshot`

## 招标清单匹配工作台

企业定额协同审核页面仍为稳定页面，访问路径为 `/`；招标清单匹配页是并列新增页面，访问路径为 `/bid`。

招标清单匹配页读取本地 PostgreSQL `import_bid_records` 暂存表，并将导入行按只读 view model 展示到 `web_bid_*` 表中。该流程不修改 `import_bid_records`，不保存匹配结果，不做成本测算，不生成 `approved`，后续阶段才会增加 `bid_item_mapping_draft`。

### item_code 规范化规则

- 去除空格、短横线和特殊字符，只保留数字。
- 12 位编码按前 9 位生成 `bill_code_9`，后 3 位作为 `item_suffix`。
- 11 位编码按缺首位 `0` 处理，补 `0` 后再按 12 位编码拆分。
- 9 位编码直接作为 `bill_code_9`，`item_suffix` 留空。
- 其他长度标记为 `item_code_parse_failed`，只做红色风险提示和人工复核提示。

### 招标清单只读 API

- `GET /api/bid/summary`
- `GET /api/bid/tree`
- `GET /api/bid/item/{bid_item_id}`
- `GET /api/bid/item/{bid_item_id}/candidates`
- `GET /api/bid/search?q=`

### BID-COLLAB-UI-STRUCTURE-ALIGNMENT-1

本轮将 `/bid` 调整为高信息密度核对工作台，而不是候选池平铺页面：

- 左侧为项目 / 专业 / 分部工程树，只用于定位和过滤清单分类。
- 中间主表按“清单项 -> Top 推荐定额 / 补子目 -> 候选池标记”的层级显示。
- 底部候选池默认只显示 Top 推荐，可切换全部候选，并支持分组、类型和风险过滤；底部高度可拖拽。
- 右侧详情显示当前清单行或定额行的 Item Code、bill_code_9、名称、单位、工程量、项目特征、编码-名称一致性和风险提示。
- 左侧、右侧、底部 splitter 尺寸保存到 localStorage。

新增只读 API：

- `GET /api/bid/item/{bid_item_id}/composition_preview`
- `GET /api/bid/item/{bid_item_id}/candidate_pool`
- `GET /api/bid/item/{bid_item_id}/consistency`

治理边界保持不变：本阶段不修改 GB/T baseline、GD2018 baseline、mapping reference 或 `import_bid_records`，不生成 `bid_item_mapping_draft`，不生成 `approved`。

### BID-COLLAB-STANDARD-FIRST-STRUCTURE-1

本轮将 `/bid` 调整为“国标清单标准优先”的信息架构：

- 左侧主导航改为 GB/T 50854 国标清单标准树，层级为 appendix -> section -> bill。
- 投标文件 / 投标分部 / 自定义分类降级为辅助筛选器，不再作为主树。
- 中间主表按 `GB/T bill_code_9 -> bid item instance -> GD2018 quota / enterprise supplement` 展示。
- 每个 bid item 默认只展开 Top 推荐定额 / 补子目，低优先级候选保留在底部候选池。
- 未匹配 GB/T baseline 的投标清单进入“未匹配 / 人工处理”分组。
- 本阶段仍为只读预览，不保存 bid mapping draft，不做成本测算，不生成 `approved`。

新增只读 API：

- `GET /api/bid/gb-standard-tree`
- `GET /api/bid/source-filters`
- `GET /api/bid/gb-bill/{bill_code_9}/items`
- `GET /api/bid/gb-bill/{bill_code_9}/composition`

既有企业定额审核页 `/`、draft save / autosave / localStorage / snapshot / audit snapshot 能力保持隔离。

### BID-COLLAB-RECOVER-COMPACT-READONLY-1

本轮将 `/bid` 从 Glodon-oriented exploratory layout 恢复为 compact readonly prototype：

- 左侧保留 GB/T standard tree（appendix -> section -> bill）作为主导航；投标来源只作为筛选器。
- 中间主表恢复为 `GB/T bill -> bid item instance -> recommended quota / enterprise supplement` 的折叠层级。
- 底部仅保留 candidate pool，不再展示 bottom multi-tab、候选查询面板或“清单索引 / 清单 / 定额 / 人材机 / 我的数据”等入口。
- 右侧只显示当前清单行 / 定额行详情、编码-名称一致性和风险提示。
- 恢复版前端不再调用 `/feature-content`、`/quantity-detail`、`/price-breakdown`、`/candidate-query-panel` 等 Glodon-oriented readonly APIs；这些后端接口如仍存在，仅作为历史探索接口保留。
- 本轮仍为只读预览：不生成 `bid_item_mapping_draft`，不生成 `approved`，不修改 GB/T baseline、GD2018 baseline、mapping reference 或 `import_bid_records`。

## A.1.1 PDF 定额明细展示工作台

访问路径：`/quota-a111`

该页面是独立的只读展示闭环，不是企业定额协同审核页，也不是招标清单匹配页。它以 GD2018 PDF A.1.1 full review pack 为省定额主项、工料机、工作内容、工程量规则和 PDF/XLSX 对账来源；mapping candidate 仅用于把 A1-1-* 候选挂到 GB/T Appendix A 清单。

页面结构：

- 左侧：GB/T Appendix A 土石方工程清单树，层级为 appendix -> section -> bill。
- 中间：`GB/T bill -> GD2018 A1-1 PDF quota candidate -> xlsx-only supplemental candidate`。
- 下侧：工料机显示、工作内容、工程量规则、PDF/XLSX 对账、Issues。
- 右侧：当前 bill/quota 的 PDF 页码、书内页码、coverage_status、risk 和 review_status 摘要。

新增只读 API：

- `GET /api/quota-a111/tree`
- `GET /api/quota-a111/bill/{bill_code_9}/rows`
- `GET /api/quota-a111/quota/{quota_source_code}/detail`
- `GET /api/quota-a111/quota/{quota_source_code}/resources`
- `GET /api/quota-a111/quota/{quota_source_code}/work-content`
- `GET /api/quota-a111/quota/{quota_source_code}/quantity-rule`
- `GET /api/quota-a111/quota/{quota_source_code}/reconciliation`
- `GET /api/quota-a111/search?q=`

治理边界：

- 不重新解析 PDF。
- 不写生产数据库。
- 不修改 GB/T baseline、GD2018 PDF candidate、normalized Excel 或 mapping candidate。
- 不生成 `approved`。
- 不生成 `internal_price_library`。
- 不做成本测算。

### WEB-QUOTA-A111-MAPPING-DRAFT-1

本阶段在 `/quota-a111` 保持原有三栏与底部 tabs 结构的基础上，增加草稿级 mapping edge 调整能力：

- 中间主表的 A1-1-* 候选行、XLSX-only 补充行、`draft_copy` 和 `draft_move_target` 行可拖动。
- 拖动的对象不是省定额子目本体，而是 `GB/T bill_code_9 -> GD2018 quota_source_code` 的候选关系草稿。
- 支持拖到左侧 GB/T bill 节点或中间主表 `gb_bill` 行。
- 放下后必须确认 Copy / Move / Exclude / Cancel；Copy 是默认推荐，Move 不默认。
- Copy 生成 `draft_copy`，原关系保留。
- Move 生成 `draft_move_target`，并在草稿 overlay 中把 source relation 标为 `draft_move_source_excluded`。
- Exclude 生成 `draft_excluded`，默认隐藏，可通过“显示被排除草稿”查看。
- Restore 只把草稿 edge 标记为 `reverted`，恢复原始候选显示。
- 中间主表整行任意单元格可点击选中，编码按钮不再是唯一入口。

草稿只写本地 SQLite：

- `web_quota_a111_mapping_draft_edges`
- `web_quota_a111_mapping_draft_audit_log`

新增草稿 API：

- `GET /api/quota-a111/draft/edges`
- `POST /api/quota-a111/draft/edge`
- `POST /api/quota-a111/draft/edge/{draft_edge_id}/revert`
- `GET /api/quota-a111/draft/export`
- `GET /api/quota-a111/draft/audit/export`
- `POST /api/quota-a111/draft/reset-test-data`
- `GET /api/quota-a111/draft/stats`

治理边界保持不变：不修改原始 mapping candidate，不移动省定额 source_code，不修改名称、单位、四费或工料机明细，不生成 approved，不做成本测算，不写生产数据库。

### WEB-QUOTA-A111-DRAFT-COUNTS-DETAIL-REFINEMENT-1

本阶段在现有 `/quota-a111` 页面结构内做三项局部细化：

- 左侧 GB/T bill 节点的数量由后端根据原始唯一关系和本地 SQLite active draft edge 动态计算。字段包括 `original_candidate_count`、`copy_in_count`、`move_in_count`、`move_out_count`、`excluded_count`、`reverted_count`、`effective_candidate_count` 和 `draft_active_count`。
- 有效数量按 `original + copy_in + move_in - move_out - excluded` 计算；同一 `bill_code_9 + quota_source_code` 只计一次，reverted edge 不再影响有效数量。
- 左树使用业务语义颜色：原始绿色、Copy 黄色、Move 迁入蓝色、Move 迁出红色、Exclude 灰红色、有效总数深色。操作成功后重新请求 `/api/quota-a111/tree`，不依赖前端临时计数。
- 工作内容使用序号拆分后的表格展示，并通过“查看原文”保留完整来源文本；无法可靠拆分时使用 `raw_fallback` 和 `needs_manual_review`。
- 工程量规则使用“索引表 + 选中规则详情”展示，索引区与详情区可拖动调整高度。源规则的适用范围仍需人工确认时，展示模型保留 `rule_scope=uncertain`。

扩展后的只读 API：

- `GET /api/quota-a111/tree`：bill node 包含逐项草稿统计。
- `GET /api/quota-a111/quota/{quota_source_code}/work-content`：返回 `items`、`raw_text` 和 fallback 统计。
- `GET /api/quota-a111/quota/{quota_source_code}/quantity-rule`：返回 `rule_groups`、clauses、`raw_text` 和 scope 状态。

展示模型输出到：

`data/private/reference_extraction/runs/WEB_QUOTA_A111_DRAFT_COUNTS_DETAIL_REFINEMENT_1/`

该目录仍属于 private artifact，不提交 Git。文本拆分仅用于 Web 展示，不回写 PDF Candidate、normalized Excel 或原始 mapping candidate；Copy / Move / Exclude / Restore 仍只写本地 Web Prototype SQLite，不生成 approved。

### WEB-QUOTA-A111-QUANTITY-RULE-DUAL-VIEW-1

本阶段只优化 `/quota-a111` 底部“工程量规则”页签，将规则信息分为三层：

- Evidence Layer：原始广东省定额 PDF、SHA256、PDF 页码、书内页码、水印和原页面表格。
- Semantic Layer：去重后的唯一 rule block，包含规则号、层级、标题、摘要和来源页。
- Applicability Layer：独立 scope link，描述章节、定额区间或 specific quota 关联，不再把同一规则复制到每个 quota。

4,521 条旧展示记录由 33 个结构块分别复制到 137 个 quota 形成。本阶段不修改旧记录，而是生成 33 个 `quantity_rule_source_blocks` 和 33 个 `quantity_rule_scope_links` 供新视图只读查询。

工程量规则页签提供三个子视图：

- 原文视图：默认视图，直接嵌入未修改的原始 PDF，支持上一页、下一页、适应宽度、放大、缩小和独立滚动。
- 结构化视图：保留规则索引，显示 rule block、层级、标题、摘要、uncertain scope 和来源页；点击规则跳转对应原始 PDF 页。
- 对照视图：左侧规则索引与适用范围，右侧原始 PDF 页面。现有数据没有可靠 bbox，因此只跳页，不伪造高亮。

现有抽取未可靠保留表格行列关系，因此 `table_json` 留空，表格统一由原 PDF 页面呈现；不使用 OCR，不猜测列结构，不删除水印。

新增只读 API：

- `GET /api/quota-a111/quota/{quota_source_code}/quantity-rule/source-pages`
- `GET /api/quota-a111/quantity-rule/block/{rule_block_id}`
- `GET /api/quota-a111/quantity-rule/page/{pdf_page_no}`
- `GET /api/quota-a111/quota/{quota_source_code}/quantity-rule/structured`
- `GET /api/quota-a111/quantity-rule/source-pdf`

新模型输出到：

`data/private/reference_extraction/runs/WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1/`

治理边界不变：不修改 PDF Candidate、Mapping Candidate 或 Mapping Draft schema，不写生产数据库，不生成 approved，不进入企业价格与成本测算。
