// Simple test using CommonJS require
const axios = require('axios');

async function testLMStudio() {
  console.log('🔍 Testing LM Studio connection...');
  
  try {
    // Test basic server connection
    const healthUrl = 'http://localhost:1234/v1/models';
    console.log(`\n🔄 Connecting to ${healthUrl}...`);
    
    const response = await axios.get(healthUrl, {
      timeout: 10000
    });
    
    console.log('✅ Successfully connected to LM Studio!');
    console.log('\n📋 Available models:');
    
    if (response.data && response.data.data) {
      response.data.data.forEach((model, i) => {
        console.log(`   ${i + 1}. ${model.id}`);
      });
    } else {
      console.log('   No models found');
    }
    
    // Test chat completion if we have models
    if (response.data && response.data.data && response.data.data.length > 0) {
      console.log('\n🔄 Testing chat completion...');
      
      const completion = await axios.post(
        'http://localhost:1234/v1/chat/completions',
        {
          model: response.data.data[0].id,
          messages: [
            { role: 'system', content: 'You are a helpful assistant.' },
            { role: 'user', content: 'Say "Hello from the test script!"' }
          ]
        },
        {
          timeout: 30000
        }
      );
      
      console.log('✅ Chat completion response:');
      console.log(completion.data.choices[0].message.content);
    }
    
  } catch (error) {
    console.error('\n❌ Error connecting to LM Studio:');
    
    if (error.response) {
      console.error('Status:', error.response.status);
      console.error('Data:', error.response.data);
    } else if (error.request) {
      console.error('No response received:', error.message);
      console.error('Is LM Studio running and the server active?');
    } else {
      console.error('Error:', error.message);
    }
    
    process.exit(1);
  }
}

testLMStudio();
