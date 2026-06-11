# 工程項目成本管理系統代碼檢查與指導意見書

生成日期：2026-06-09

檢查目標：

> 以 ERP 思想約束數據可信度，以 Odoo 學習模塊化工程，以低代碼系統沉澱業務流程，以 Codex 重構一套專業、可控、可追溯的工程項目成本管理系統。

## 一、總體判斷

當前項目已經具備一個「工程造價 Excel 解析原型」的雛形，核心能力集中在投標清單 Excel 上傳、表頭識別、字段映射、行分類、記錄標準化、入庫和導出。從文檔看，項目已意識到 `import_bid_records -> review -> bid_records` 的 ERP 式分層流程，也開始拆分 `api / services / models / utils / docs`。

但若以「專業、可控、可追溯的工程項目成本管理系統」為目標，當前仍處於原型階段，尚未形成 ERP 級別的業務閉環、權限邊界、審計追蹤、主數據治理和可靠工程結構。最需要先補的是：數據可信鏈路、業務狀態機、模塊化邊界、數據庫約束、測試與部署可重現性。

一句話結論：

> 現在是「Excel Parser + 入庫腳本 + 初步分析」；目標應演進為「以項目為中心、以合同/預算/成本/變更/結算為主線、以審批和審計為約束的工程成本 ERP 子系統」。

## 二、當前代碼現狀

### 1. 已有能力

項目入口位於 `main.py`，已使用 FastAPI 並掛載項目與投標 API：

- `api/project_api.py` 提供 `/projects/portfolio-health/`，查詢項目組合健康度並調用 AI 報告。
- `api/bid_api.py` 提供 `/upload-bid-excel/`、`/excel-sheet-names/`、`/export-bid-records`。
- `services/excel_row_parser.py` 負責 Excel 行分類。
- `services/excel_row_pipeline.py` 負責表頭合併、schema 構造、上下文附加、邏輯記錄構造、標準化。
- `services/db_service.py` 負責寫入 `import_bid_records` 和 `bid_records`。
- `utils/column_mapping.py` 已按 basic、bid、material、cost、tax、project、supplier、labor、contract 等映射拆分，這是模塊化的好苗頭。
- `docs/DATABASE.md` 已設計了導入暫存表和正式業務表。

### 2. 與目標一致的亮點

- 已有「導入暫存表」意識：`docs/DATABASE.md` 中設計 `import_bid_records` 作為 staging table，這符合 ERP 中「原始導入不可直接污染正式業務數據」的思想。
- 已有「審核後同步」意識：文檔設計了 `pending / approved / rejected / synced` 狀態。
- 已開始建立字段映射中心：`utils/mappings/*` 能逐步演變為工程成本主數據的映射層。
- 已將 Excel 解析拆成多個 pipeline 步驟，方便後續引入可追溯的處理節點。

## 三、主要差距

### 1. 數據可信度不足

目前數據可信度主要依賴解析過程和簡單校驗，但沒有形成完整的可信鏈。

主要問題：

- `api/bid_api.py` 上傳文件後直接寫入 `uploads/{file.filename}`，缺少文件名清洗、批次號、文件哈希、原始文件歸檔、操作者、導入時間、來源 sheet 等追蹤信息。
- `services/db_service.py` 寫入 `import_bid_records` 時只保存業務字段，沒有落庫 `batch_id`、`source_file_name`、`source_sheet_name`、`source_row_index`、`review_status`，與 `docs/DATABASE.md` 的設計不一致。
- `services/excel_row_pipeline.py` 中已在 `attach_context_to_main_rows` 設計了 `source_row_index`，但主流程實際使用的是 `attach_category` 和 `build_logical_records`，導致來源行號沒有進入標準記錄。
- `services/data_quality.py` 只有字段缺失與負數檢查，缺少合計校驗、工程量單位校驗、清單編碼規則、同批次重複檢查、金額等式校驗：`quantity * unit_price ≈ total_price`。
- 數據庫連接在 `utils/db.py` 中以全局 `conn/cursor` 方式建立，缺少連接池、事務邊界、回滾、錯誤隔離和請求級資源管理。

方向：

> 導入數據必須能回答四個問題：從哪個文件來、誰導入、哪一行生成、經過哪些規則修改或確認。

### 2. 業務流程沒有閉環

文檔中已經有 review 和 sync，但代碼中尚未實現：

- `docs/API.md` 描述了 `/import-records`、`/review-import-records`、`/sync-import-records`，但 `api/bid_api.py` 中沒有這些接口。
- `insert_many_records()` 是逐條插入，沒有批次級事務；中間失敗會造成部分寫入。
- 正式表 `bid_records` 與導入表 `import_bid_records` 的同步關係沒有真正落地。
- 缺少審批意見、審批人、審批時間、駁回原因、修改記錄。

方向：

> 先建立「導入 -> 校驗 -> 待審 -> 審核 -> 入正式表 -> 可分析」的最小業務狀態機，再談 AI 分析。

### 3. Odoo 式模塊化不足

Odoo 的核心啟發不是照搬框架，而是學習它的模塊邊界：

- 每個業務域有自己的 model、service、view/api、security、workflow、data。
- 模塊之間通過清晰的業務對象關聯，而不是共享全局 cursor 或散落函數。

當前項目雖有目錄分層，但業務模塊尚未形成：

- 投標清單、項目、成本、合同、材料、人工、供應商等還只是 mapping 概念，沒有成為獨立業務模塊。
- `models/schemas.py` 只有 `ProjectHealth`，缺少 `Project`、`ImportBatch`、`ImportBidRecord`、`BidRecord`、`ReviewAction`、`CostItem`、`Contract` 等核心模型。
- `api/cost_api.py` 是空文件，成本管理主線尚未建立。
- `services/cost_service.py` 直接 SQL 聚合 `projects` 和 `costs`，但項目成本來源、口徑、狀態、版本不可追蹤。

方向：

> 按 Odoo 思路，不要先堆接口；應先定業務模型，再定狀態，再定權限，再定視圖/API。

### 4. 低代碼流程沉澱尚未開始

低代碼不是簡單拖拽頁面，而是把業務規則配置化、流程狀態可視化、審批節點數據化。

當前缺失：

- 沒有流程定義表，如 `workflow_definitions`、`workflow_nodes`、`workflow_transitions`。
- 沒有規則配置表，如字段必填、金額容差、清單編碼格式、超預算預警閾值。
- 沒有表單 schema 或字段權限配置。
- 規則寫死在 Python 代碼中，例如 `data_quality.py`、`rule_engine.py`。

方向：

> 將「校驗規則、審批流、字段映射、成本分類、預警閾值」逐步從硬編碼轉為配置，這才是低代碼沉澱業務流程的起點。

### 5. 可運行性與工程可控性有明顯風險

檢查中發現：

- 多個文件存在中文亂碼，尤其是 `services/rule_engine.py`、`services/intelligence_engine.py`、`services/data_quality.py`、`services/excel_row_parser.py`、`docs/ARCHITECTURE.md`。
- `services/rule_engine.py`、`services/intelligence_engine.py`、`services/data_quality.py` 中疑似存在字符串未閉合問題，可能導致 Python 語法錯誤。
- 本地 `.venv` 的 Python 啟動失敗，提示指向的 `C:\Users\haozh\AppData\Local\Programs\Python\Python311\python.exe` 不可用，說明虛擬環境不可重現。
- `services/ai_analysis.py` 在模塊 import 時打印 `DEEPSEEK_API_KEY`，有密鑰泄露風險。
- `.env.example` 只包含 `OPENAI_API_KEY`，但代碼實際使用 PostgreSQL 和 `DEEPSEEK_API_KEY`，環境配置不完整。
- 缺少 `pytest`、CI、格式化、lint、遷移工具、啟動腳本和測試數據。

方向：

> 工程系統先要「能穩定啟動、能重複部署、能自動驗證」，否則越往業務上加功能，越難控制。

## 四、目標架構建議

建議把系統重構為以下模塊：

```text
app/
  core/                  # 配置、日誌、權限、數據庫、異常
  modules/
    project/             # 項目主數據
    bid/                 # 投標/清單導入
    cost/                # 成本台賬、成本歸集、成本分析
    contract/            # 合同、變更、簽證、結算
    supplier/            # 供應商
    material/            # 材料主數據與價格
    workflow/            # 審批流、狀態機、任務
    audit/               # 審計日誌、版本、操作追蹤
    rule/                # 配置化規則引擎
    ai/                  # AI 分析、提示詞、結果存證
  integrations/
    excel/               # Excel 解析與導出
    odoo/                # 未來如需對接 Odoo，可放此處
  tests/
  migrations/
```

核心業務鏈路：

```text
項目 Project
  -> 合同 Contract
  -> 預算 Budget
  -> 清單 Bid BOQ
  -> 成本 Cost Ledger
  -> 變更 Change Order
  -> 簽證 Site Instruction
  -> 結算 Settlement
  -> 分析 Analysis
```

數據可信鏈路：

```text
SourceFile
  -> ImportBatch
  -> RawRow
  -> ParsedRecord
  -> QualityIssue
  -> ReviewAction
  -> ApprovedBusinessRecord
  -> AuditLog
```

## 五、優先落地路線

### P0：先恢復可運行與可驗證

目標：系統能穩定啟動、測試能跑、錯誤能暴露。

建議任務：

- 修復中文編碼與疑似語法錯誤，統一所有源碼為 UTF-8。
- 重建 `.venv` 或提供 `pyproject.toml` / `requirements.lock`。
- 補齊 `.env.example`：`DB_HOST`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`、`DB_PORT`、`DEEPSEEK_API_KEY`。
- 移除 `services/ai_analysis.py` 中 import 時打印 API key 的代碼。
- 增加 `pytest`，先覆蓋 Excel 解析、金額校驗、入庫前校驗。

驗收標準：

- `uvicorn main:app --reload` 可啟動。
- `pytest` 可通過。
- 任意 API import 不會直接連外部 AI，也不會打印密鑰。

### P1：建立導入批次與可信數據鏈

目標：每條記錄都有來源、批次、行號、質量結果。

建議新增表：

- `source_files`
- `import_batches`
- `import_bid_records`
- `quality_issues`
- `review_actions`
- `audit_logs`

建議字段：

- `batch_id`
- `source_file_name`
- `source_file_hash`
- `source_sheet_name`
- `source_row_index`
- `parser_version`
- `mapping_version`
- `quality_score`
- `review_status`
- `created_by`
- `created_at`

驗收標準：

- 上傳一次 Excel 生成一個 batch。
- 每條導入記錄能追溯到原文件、sheet、行號。
- 校驗結果不只返回給前端，也要落庫。

### P2：補齊審核與同步流程

目標：暫存數據不能直接進正式業務表。

建議接口：

- `GET /import-batches`
- `GET /import-batches/{batch_id}/records`
- `POST /import-records/{id}/approve`
- `POST /import-records/{id}/reject`
- `POST /import-batches/{batch_id}/sync`

狀態機：

```text
uploaded
  -> parsed
  -> quality_checked
  -> pending_review
  -> approved / rejected
  -> synced
```

驗收標準：

- 只有 `approved` 記錄可以同步到正式表。
- 每次審核都有操作人、時間、意見。
- 同步過程使用事務，失敗可回滾。

### P3：按業務域重構模塊

目標：從技術目錄分層演進到 Odoo 式業務模塊。

優先模塊：

- `project`：項目主數據、預算、狀態。
- `bid`：清單導入、清單項、清單版本。
- `cost`：成本台賬、成本分類、成本歸集。
- `workflow`：審批狀態機。
- `audit`：操作日誌與版本追蹤。

驗收標準：

- API 不直接拼業務流程，業務規則收斂在 service/domain 層。
- 數據庫訪問不再使用全局 cursor。
- 每個模塊有自己的 schema、repository、service、router、tests。

### P4：引入配置化規則與低代碼流程

目標：把規則從代碼中抽出來，讓業務流程可配置、可版本化。

可先配置化的內容：

- Excel 字段映射。
- 成本分類關鍵詞。
- 必填字段。
- 金額容差。
- 預警閾值。
- 審批節點與角色。

建議配置表：

- `rule_sets`
- `rule_items`
- `workflow_definitions`
- `workflow_nodes`
- `workflow_transitions`
- `form_schemas`

驗收標準：

- 修改成本分類不需要改 Python 代碼。
- 不同項目類型可使用不同校驗規則。
- 審批流程可版本化，歷史單據保留當時流程版本。

### P5：AI 能力納入可追溯框架

目標：AI 是輔助分析，不是不可控的黑箱決策。

建議：

- AI 分析輸入必須保存：數據範圍、查詢條件、prompt version。
- AI 輸出必須保存：模型、時間、結果、人工確認狀態。
- AI 報告只對 `approved/synced` 的可信數據生成。
- AI 發現異常後生成 `quality_issues` 或 `risk_flags`，等待人工確認。

驗收標準：

- 任意 AI 結論可追溯到輸入數據與提示詞版本。
- AI 不直接修改正式業務數據。
- AI 建議進入審核流程，而不是繞過流程。

## 六、數據庫設計方向

建議由「單表記錄」演進為「主數據 + 交易數據 + 審計數據」。

主數據：

- `projects`
- `suppliers`
- `materials`
- `cost_categories`
- `users`
- `roles`

交易數據：

- `source_files`
- `import_batches`
- `import_bid_records`
- `bid_records`
- `cost_entries`
- `contracts`
- `change_orders`
- `settlements`

治理數據：

- `quality_issues`
- `review_actions`
- `audit_logs`
- `record_versions`
- `rule_sets`
- `workflow_instances`

關鍵約束：

- 金額字段使用 `numeric`，不要用 float 作為財務落庫類型。
- 所有正式業務表都應有 `created_at`、`created_by`、`updated_at`、`updated_by`。
- 所有導入記錄必須有 `batch_id`。
- 正式記錄應保留 `import_record_id`，建立來源追蹤。
- 對項目、合同、清單版本建立唯一約束和外鍵約束。

## 七、對 Codex 重構工作的建議

Codex 應作為「可控重構助手」，不要一次性大改。建議採用小步閉環：

1. 先讓項目可啟動、可測試。
2. 為現有 Excel parser 補最小測試。
3. 補導入批次模型與 migration。
4. 改造 `/upload-bid-excel/`，讓它產生 batch 和 source trace。
5. 增加審核 API。
6. 增加同步 API。
7. 再重構模塊目錄。
8. 最後引入低代碼規則表與 AI 存證。

每一步都應要求 Codex 交付：

- 修改文件清單。
- 測試命令與結果。
- 數據庫變更說明。
- 回滾方案。
- 未完成風險。

## 八、近期三個里程碑

### 里程碑 1：可信導入 MVP

時間建議：1-2 週。

交付：

- Excel 上傳批次化。
- 原始文件 hash。
- 每行 source trace。
- 質量報告落庫。
- 導入批次查詢 API。

### 里程碑 2：審核同步 MVP

時間建議：1-2 週。

交付：

- 待審列表。
- 單條/批量審核。
- 駁回原因。
- approved 記錄同步正式表。
- 審核日誌。

### 里程碑 3：項目成本主線 MVP

時間建議：2-4 週。

交付：

- 項目主數據。
- 預算與清單版本。
- 成本分類。
- 成本台賬。
- 成本偏差分析。
- 可追溯報表。

## 九、最終建議

本項目不要急於做大而全的 ERP，也不要先做 AI 報告展示。最正確的路徑是：

```text
先可信
再流程
再模塊
再配置
再智能
```

也就是：

1. 先把 Excel 導入變成可信數據入口。
2. 再把審核、同步、審計做成業務閉環。
3. 再按 Odoo 思路拆成項目、投標、成本、合同、工作流等模塊。
4. 再把規則、字段、流程沉澱為低代碼配置。
5. 最後讓 AI 在可追溯的數據和流程上工作。

若按這個方向推進，該系統可以從目前的「工程 Excel 解析原型」逐步演進為一套真正能服務工程項目成本管理的專業平台。
