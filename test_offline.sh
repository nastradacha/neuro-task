#!/bin/bash
echo "=== OFFLINE MODE TEST ==="

# 1. Create task while offline
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task":"Test Offline"}'

# 2. Create offline task
echo "Creating offline task..."
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task":"Offline Task"}'

# 3. Show pending syncs
sqlite3 tasks.db "SELECT * FROM sync_metadata WHERE sync_status = 'pending';"

# 4. Sync endpoint (update to use correct endpoint)
echo "Syncing..."
# This should be automatic via service worker, no manual endpoint needed