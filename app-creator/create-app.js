#!/usr/bin/env node

import { CascadeAppCreator } from './index.js';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs/promises';
import readline from 'readline';
import { lmStudioHelper } from './utils/lmStudioHelper.js';

// Create readline interface for user input
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// Helper function to get user input
function question(prompt) {
  return new Promise((resolve) => {
    rl.question(prompt, resolve);
  });
}

async function checkLMStudio() {
  console.log('🔍 Checking LM Studio connection...');
  
  if (!await lmStudioHelper.isServerRunning()) {
    console.log('LM Studio is not running. Attempting to start it...');
    const started = await lmStudioHelper.startLMStudio();
    
    if (!started) {
      console.error('\n❌ Failed to start LM Studio. Please make sure it is installed and try again.');
      console.log('\nYou can download LM Studio from: https://lmstudio.ai/');
      console.log('After installation, please:');
      console.log('1. Start LM Studio');
      console.log('2. Load a model');
      console.log('3. Enable the local server in Settings > Local Server');
      return false;
    }
    
    console.log('⏳ Waiting for LM Studio to be ready...');
    try {
      await lmStudioHelper.waitForServer();
    } catch (error) {
      console.error('\n❌ Timed out waiting for LM Studio to start.');
      console.log('\nPlease ensure:');
      console.log('1. LM Studio is running');
      console.log('2. A model is loaded');
      console.log('3. Local server is enabled in Settings > Local Server');
      return false;
    }
  }
  
  try {
    const model = await lmStudioHelper.getFirstAvailableModel();
    console.log(`✅ Connected to LM Studio with model: ${model}`);
    return true;
  } catch (error) {
    console.error('\n❌ No models available in LM Studio.');
    console.log('\nPlease:');
    console.log('1. Open LM Studio');
    console.log('2. Download and load a model from the home screen');
    console.log('3. Try again');
    return false;
  }
}

async function main() {
  try {
    console.log('🚀 Cascade App Creator');
    console.log('=====================\n');
    
    // Check LM Studio connection
    const isReady = await checkLMStudio();
    if (!isReady) {
      process.exit(1);
    }
    
    // Get app description from command line or prompt
    let appDescription = process.argv[2];
    
    if (!appDescription) {
      console.log('\nDescribe the app you want to create in natural language.');
      console.log('Example: "A todo list app with React and local storage"\n');
      appDescription = await question('Your app description: ');
    }

    console.log('\n🔍 Analyzing your request...');
    
    // Initialize app creator
    const appCreator = new CascadeAppCreator();
    
    // Create app
    const result = await appCreator.createApp(appDescription);
    
    if (result.success) {
      console.log('\n✅ App generated successfully!');
      console.log(`📁 Output directory: ./${result.requirements.app_name || 'my-app'}`);
      console.log('\nNext steps:');
      console.log(`1. cd ${result.requirements.app_name || 'my-app'}`);
      console.log('2. npm install');
      console.log('3. npm start\n');
    } else {
      console.error('\n❌ Failed to create app:', result.error);
    }
  } catch (error) {
    console.error('\n❌ An error occurred:', error.message);
    process.exit(1);
  } finally {
    rl.close();
  }
}

main();
