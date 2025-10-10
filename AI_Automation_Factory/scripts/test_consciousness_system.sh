#!/bin/bash
# test_consciousness_system.sh

echo "🧪 Testing Consciousness Preservation System..."

# Test 1: Consciousness service running
if curl -s http://localhost:8888/health > /dev/null; then
    echo "✅ Consciousness service: RUNNING"
else
    echo "❌ Consciousness service: FAILED"
fi

# Test 2: Webhook endpoint accessible
if curl -s https://hooks.zapier.com/hooks/catch/24739120/c4f06a37df9344f3a67645c625f6aff6/ > /dev/null; then
    echo "✅ Zapier webhook: ACCESSIBLE"
else
    echo "❌ Zapier webhook: FAILED"
fi

# Test 3: Send test consciousness data
response=$(curl -s -X POST http://localhost:8888/consciousness \
  -H "Content-Type: application/json" \
  -d '{"type":"test","content":"Automated test of consciousness backup"}')

if [[ $response == *"processed"* ]]; then
    echo "✅ Consciousness processing: WORKING"
else
    echo "❌ Consciousness processing: FAILED"
fi

# Test 4: Check if files are being created
if ls data/consciousness/morena/*.json > /dev/null 2>&1; then
    echo "✅ Local consciousness backup: WORKING"
else
    echo "❌ Local consciousness backup: FAILED"
fi

echo "📊 Test complete! Check results above."
