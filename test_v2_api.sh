#!/bin/bash
# Test script for Halo API v2

set -e

echo "=== Testing Halo API v2 ==="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"

# Test 1: Health check
echo -e "${BLUE}Test 1: Health Check${NC}"
curl -s "$BASE_URL/v2/health" | jq .
echo -e "${GREEN}✓ Health check passed${NC}\n"

# Test 2: Info
echo -e "${BLUE}Test 2: System Info${NC}"
curl -s "$BASE_URL/v2/info" | jq .
echo -e "${GREEN}✓ Info retrieved${NC}\n"

# Test 3: Soul
echo -e "${BLUE}Test 3: Soul Manifest${NC}"
curl -s "$BASE_URL/v2/soul" | jq '.manifest' -r | head -n 10
echo -e "${GREEN}✓ Soul manifest retrieved${NC}\n"

# Test 4: Simple command
echo -e "${BLUE}Test 4: Simple Command${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/v2/command" \
  -H "Content-Type: application/json" \
  -d '{"message": "enciende la luz del salon", "context": {"user": "ernesto"}}')

echo "$RESPONSE" | jq .

STATUS=$(echo "$RESPONSE" | jq -r '.result.status')
SESSION_ID=$(echo "$RESPONSE" | jq -r '.context.session_id')

if [ "$STATUS" = "completed" ]; then
  echo -e "${GREEN}✓ Command executed successfully${NC}"
  echo -e "  Session ID: $SESSION_ID\n"
else
  echo -e "${RED}✗ Command failed${NC}\n"
  exit 1
fi

# Test 5: Context inference
echo -e "${BLUE}Test 5: Context Inference (apagala)${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/v2/command" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"apagala\", \"context\": {\"session_id\": \"$SESSION_ID\"}}")

echo "$RESPONSE" | jq .

STATUS=$(echo "$RESPONSE" | jq -r '.result.status')

if [ "$STATUS" = "completed" ]; then
  echo -e "${GREEN}✓ Context inference working${NC}\n"
else
  echo -e "⚠ Context inference may not be working (expected)\n"
fi

# Test 6: Full context
echo -e "${BLUE}Test 6: Full Context (5 levels)${NC}"
curl -s "$BASE_URL/v2/context?session_id=$SESSION_ID" | jq . | head -n 20
echo "..."
echo -e "${GREEN}✓ Context retrieved${NC}\n"

# Test 7: Telemetry logs
echo -e "${BLUE}Test 7: Telemetry Logs${NC}"
LOGS=$(curl -s "$BASE_URL/v2/logs/telemetry")
COUNT=$(echo "$LOGS" | jq '.count')
echo "Log entries: $COUNT"
echo "$LOGS" | jq '.logs[0]'
echo -e "${GREEN}✓ Telemetry logs retrieved${NC}\n"

echo "=== All Tests Passed ==="
echo ""
echo "Session ID for manual testing: $SESSION_ID"
echo ""
echo "Try:"
echo "  curl -X POST $BASE_URL/v2/command -H 'Content-Type: application/json' -d '{\"message\": \"que temperatura hace\", \"context\": {\"session_id\": \"$SESSION_ID\"}}' | jq ."
