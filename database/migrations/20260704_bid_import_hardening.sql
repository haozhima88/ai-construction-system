ALTER TABLE import_bid_records
ADD COLUMN IF NOT EXISTS source_sheet_index INTEGER;

ALTER TABLE import_bid_records
ADD COLUMN IF NOT EXISTS source_excel_row_no INTEGER;

ALTER TABLE import_bid_records
ADD COLUMN IF NOT EXISTS parser_confidence NUMERIC DEFAULT 1.0;

ALTER TABLE import_bid_records
ADD COLUMN IF NOT EXISTS parse_status TEXT DEFAULT 'parsed';

ALTER TABLE import_bid_records
ADD COLUMN IF NOT EXISTS parse_warnings TEXT;

ALTER TABLE import_bid_records
ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
