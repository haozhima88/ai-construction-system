# Standard Cost Item Reference MVP

## 1. 目标

本 MVP 为 `construction_cost_knowledge_engine` 增加一张独立的 `standard_cost_item_reference` 参考候选表，并提供 A.1.1 土石方工程的 mock seed、导入脚本、预览脚本和隔离测试。

本层只承载标准成本项参考候选，不代表企业最终标准名称。所有记录默认 `review_status = pending`，必须经过成本部人工审核后才可进入后续企业标准映射。

## 2. 数据边界

本 MVP 只允许写入：

- `standard_cost_item_reference`
- `data/mock/standard_cost_reference_mvp.sqlite`

本 MVP 不写入：

- `internal_price_library`
- `cost_items`
- `knowledge_review_records`
- `quota_to_bill_mapping`
- 主 Web 数据库
- bid parser 相关流程

## 3. 表结构摘要

`standard_cost_item_reference` 采用候选参考库结构：

- `id`
- `source_type`
- `source_name`
- `source_file`
- `source_page`
- `chapter_code`
- `chapter_name`
- `section_code`
- `section_name`
- `item_group_name`
- `source_code`
- `standard_name_candidate`
- `unit`
- `work_content`
- `keywords`
- `aliases`
- `feature_template`
- `extraction_confidence`
- `review_status`
- `reviewer`
- `remark`
- `created_at`

本 MVP seed 中 `source_type = gd_quota_2018`，`chapter_code = A.1.1`，`review_status = pending`。

## 4. Seed 文件

Seed 文件：

`data/mock/standard_cost_item_reference_A111_seed.csv`

当前 seed 覆盖 A.1.1 的三个小节：

- A.1.1.1 土方工程
- A.1.1.2 石方工程
- A.1.1.3 回填方及其他

该 seed 是用于打通 MVP 的 mock reference candidate，不作为官方完整定额库，也不作为企业最终 standard_name。

## 5. 脚本

导入：

```powershell
python scripts/import_standard_reference_seed.py
```

预览：

```powershell
python scripts/preview_standard_reference.py
```

导入脚本会先删除 `source_type = gd_quota_2018` 且 `chapter_code = A.1.1` 的旧记录，再重新导入 seed，因此可重复执行。

## 6. 测试

```powershell
python -m pytest tests/test_standard_reference_seed.py
```

测试覆盖：

- 表可以由初始化迁移创建
- seed 导入成功
- 导入记录数不少于 30
- 所有 seed 记录均为 `source_type = gd_quota_2018`
- 所有 seed 记录均为 `chapter_code = A.1.1`
- 所有 seed 记录均为 `review_status = pending`
- `standard_name_candidate` 非空
- 不写入 `internal_price_library`
- 不写入 `cost_items`
- 不写入 `knowledge_review_records`
- 重复导入不会无限增长

## 7. 后续建议

下一阶段应从官方 PDF 或已校验的结构化资料生成更完整的 A.1.1 candidate，并继续保持 `pending` 状态。企业最终标准名应通过人工审核和映射流程单独确认。
