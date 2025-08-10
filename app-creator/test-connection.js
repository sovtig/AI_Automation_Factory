// Simple test script to verify LM Studio connection
import { LMStudioClient } from '@lmstudio/sdk';

async function testConnection() {
  console.log('🔍 Testing LM Studio connection...');
  
  const client = new LMStudioClient({
    host: 'localhost',
    port: 1234,
    timeout: 30000
  });

  try {
    // Test server health
    console.log('\n🔄 Checking server health...');
    const health = await client.health();
    console.log('✅ Server health:', health);

    // List available models
    console.log('\n🔄 Listing available models...');
    const models = await client.models.list();
    console.log(`✅ Found ${models.data.length} models:`);
    models.data.forEach((model, i) => {
      console.log(`   ${i + 1}. ${model.id}`);
    });

    // Test chat completion
    if (models.data.length > 0) {
      console.log('\n🔄 Testing chat completion...');
      const response = await client.chat.completions.create({
        model: models.data[0].id,
        messages: [
          { role: 'system', content: 'You are a helpful assistant.' },
          { role: 'user', content: 'Say "Hello, LM Studio!"' }
        ]
      });
      console.log('✅ Chat completion response:');
      console.log(response.choices[0].message.content);
    }

  } catch (error) {
    console.error('❌ Error:', error.message);
    if (error.response) {
      console.error('Response status:', error.response.status);
      console.error('Response data:', error.response.data);
    }
    process.exit(1);
  }
}

testConnection().catch(console.error);
