// MongoDB initialization script
db = db.getSiblingDB('sales_db');

// Create collections
db.createCollection('raw_sales');

// Create indexes
db.raw_sales.createIndex({ "sku": 1, "ts": 1 }, { unique: true, name: "sku_ts_unique" });
db.raw_sales.createIndex({ "ts": -1 }, { name: "ts_desc" });

// Insert sample data for testing
db.raw_sales.insertMany([
  {
    "sku": "SKU-001",
    "qty": 5,
    "price": 29.99,
    "ts": "2024-01-15T10:30:00Z",
    "event_id": "test-001",
    "processed_at": new Date().getTime() / 1000
  },
  {
    "sku": "SKU-002", 
    "qty": 3,
    "price": 49.99,
    "ts": "2024-01-15T10:31:00Z",
    "event_id": "test-002",
    "processed_at": new Date().getTime() / 1000
  }
]);

print("MongoDB initialized with sample data");