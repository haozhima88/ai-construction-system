CREATE TABLE IF NOT EXISTS source_import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_name TEXT NOT NULL,
    source_file_hash TEXT,
    source_sheet_name TEXT,
    imported_at TEXT NOT NULL,
    row_count INTEGER,
    success_count INTEGER,
    warning_count INTEGER,
    error_count INTEGER,
    note TEXT
);

CREATE TABLE IF NOT EXISTS raw_cost_price_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES source_import_batches(id),
    source_row_no INTEGER NOT NULL,
    raw_category_1 TEXT,
    raw_category_2 TEXT,
    raw_item_name TEXT,
    raw_labor_price TEXT,
    raw_material_price TEXT,
    raw_machine_price TEXT,
    raw_unit TEXT,
    raw_remark TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unit_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_unit TEXT NOT NULL,
    normalized_unit TEXT NOT NULL,
    unit_type TEXT,
    note TEXT,
    UNIQUE(raw_unit)
);

CREATE TABLE IF NOT EXISTS cost_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES cost_categories(id),
    category_name TEXT NOT NULL,
    category_level INTEGER NOT NULL,
    sort_order INTEGER,
    is_active INTEGER DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_cost_categories_parent_name
ON cost_categories(COALESCE(parent_id, 0), category_name);

CREATE TABLE IF NOT EXISTS cost_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_level_1_id INTEGER REFERENCES cost_categories(id),
    category_level_2_id INTEGER REFERENCES cost_categories(id),
    item_name TEXT NOT NULL,
    normalized_item_name TEXT NOT NULL,
    unit_id INTEGER REFERENCES unit_dictionary(id),
    remark TEXT,
    source_row_no INTEGER,
    source_batch_id INTEGER REFERENCES source_import_batches(id),
    item_status TEXT DEFAULT 'active',
    quality_flags TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cost_items_normalized_name ON cost_items(normalized_item_name);
CREATE INDEX IF NOT EXISTS ix_cost_items_source ON cost_items(source_batch_id, source_row_no);

CREATE TABLE IF NOT EXISTS cost_price_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cost_item_id INTEGER NOT NULL REFERENCES cost_items(id),
    component_type TEXT NOT NULL CHECK(component_type IN ('labor', 'material', 'machine')),
    unit_price REAL,
    currency TEXT DEFAULT 'CNY',
    tax_included INTEGER,
    tax_rate REAL,
    effective_from TEXT,
    effective_to TEXT,
    source_row_no INTEGER,
    source_batch_id INTEGER REFERENCES source_import_batches(id),
    quality_flags TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_price_components_item ON cost_price_components(cost_item_id);

CREATE TABLE IF NOT EXISTS cost_item_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cost_item_id INTEGER NOT NULL REFERENCES cost_items(id),
    feature_key TEXT NOT NULL,
    feature_value TEXT NOT NULL,
    source_field TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boq_match_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cost_item_id INTEGER NOT NULL REFERENCES cost_items(id),
    positive_keywords TEXT,
    negative_keywords TEXT,
    unit_constraint TEXT,
    category_hint TEXT,
    priority INTEGER DEFAULT 100,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boq_match_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boq_line_id TEXT,
    boq_item_name TEXT,
    boq_unit TEXT,
    matched_cost_item_id INTEGER REFERENCES cost_items(id),
    match_score REAL,
    match_reason TEXT,
    need_human_review INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS v_cost_item_unit_prices AS
SELECT
    ci.id AS cost_item_id,
    cc1.category_name AS category_level_1,
    cc2.category_name AS category_level_2,
    ci.item_name,
    ud.normalized_unit AS unit,
    COALESCE(MAX(CASE WHEN cpc.component_type = 'labor' THEN cpc.unit_price END), 0) AS labor_unit_price,
    COALESCE(MAX(CASE WHEN cpc.component_type = 'material' THEN cpc.unit_price END), 0) AS material_unit_price,
    COALESCE(MAX(CASE WHEN cpc.component_type = 'machine' THEN cpc.unit_price END), 0) AS machine_unit_price,
    COALESCE(MAX(CASE WHEN cpc.component_type = 'labor' THEN cpc.unit_price END), 0)
      + COALESCE(MAX(CASE WHEN cpc.component_type = 'material' THEN cpc.unit_price END), 0)
      + COALESCE(MAX(CASE WHEN cpc.component_type = 'machine' THEN cpc.unit_price END), 0) AS total_unit_cost,
    ci.remark,
    ci.quality_flags,
    ci.source_row_no,
    ci.source_batch_id
FROM cost_items ci
LEFT JOIN cost_categories cc1 ON cc1.id = ci.category_level_1_id
LEFT JOIN cost_categories cc2 ON cc2.id = ci.category_level_2_id
LEFT JOIN unit_dictionary ud ON ud.id = ci.unit_id
LEFT JOIN cost_price_components cpc ON cpc.cost_item_id = ci.id
GROUP BY ci.id;
