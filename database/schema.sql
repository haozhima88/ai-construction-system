CREATE TABLE IF NOT EXISTS import_bid_records (
    id SERIAL PRIMARY KEY,
    batch_id TEXT,
    source_file_name TEXT,
    source_sheet_name TEXT,
    source_row_index INTEGER,
    mapping_version TEXT,
    review_status TEXT DEFAULT 'pending',
    project_name TEXT,
    category TEXT,
    serial_number TEXT,
    item_code TEXT,
    item_name TEXT,
    feature TEXT,
    unit TEXT,
    quantity NUMERIC,
    unit_price NUMERIC,
    total_price NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS bid_records (
    id SERIAL PRIMARY KEY,
    import_record_id INTEGER,
    batch_id TEXT,
    project_name TEXT,
    category TEXT,
    serial_number TEXT,
    item_code TEXT,
    item_name TEXT,
    feature TEXT,
    unit TEXT,
    quantity NUMERIC,
    unit_price NUMERIC,
    total_price NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);