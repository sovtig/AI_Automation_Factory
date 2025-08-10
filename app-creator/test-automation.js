import { CascadeAppCreator } from './index.js';
import { lmStudioHelper } from './utils/lmStudioHelper.js';
import fs from 'fs/promises';
import path from 'path';

// Test configuration
const TEST_CONFIG = {
  testAppName: 'test-todo-app',
  testDescription: 'A todo list app with React and local storage',
  timeout: 300000, // 5 minutes timeout for the entire test
  checkInterval: 5000, // Check every 5 seconds
};

class AutomationTester {
  constructor() {
    this.appCreator = new CascadeAppCreator();
    this.testDir = path.join(process.cwd(), TEST_CONFIG.testAppName);
  }

  async run() {
    console.log('🚀 Starting LM Studio Automation Test');
    console.log('==================================\n');

    try {
      // Step 1: Check LM Studio connection
      await this.checkLMStudio();
      
      // Step 2: Run the app creation test
      await this.testAppCreation();
      
      // Step 3: Verify the generated files
      await this.verifyGeneratedApp();
      
      console.log('\n✅ All tests passed successfully!');
      process.exit(0);
    } catch (error) {
      console.error('\n❌ Test failed:', error.message);
      process.exit(1);
    } finally {
      // Cleanup
      await this.cleanup();
    }
  }

  async checkLMStudio() {
    console.log('🔍 Checking LM Studio connection...');
    
    if (!await lmStudioHelper.isServerRunning()) {
      console.log('LM Studio is not running. Attempting to start it...');
      const started = await lmStudioHelper.startLMStudio();
      
      if (!started) {
        throw new Error('Failed to start LM Studio');
      }
      
      console.log('⏳ Waiting for LM Studio to be ready...');
      await lmStudioHelper.waitForServer(120000); // 2 minutes timeout
    }
    
    const model = await lmStudioHelper.getFirstAvailableModel();
    console.log(`✅ Connected to LM Studio with model: ${model}`);
  }

  async testAppCreation() {
    console.log('\n🚀 Testing app creation...');
    console.log(`Description: "${TEST_CONFIG.testDescription}"`);
    
    const result = await this.appCreator.createApp(TEST_CONFIG.testDescription);
    
    if (!result.success) {
      throw new Error(`App creation failed: ${result.error}`);
    }
    
    console.log('✅ App created successfully!');
    console.log(`📁 Output directory: ${this.testDir}`);
    
    // Save the test results
    this.testResults = result;
  }

  async verifyGeneratedApp() {
    console.log('\n🔍 Verifying generated app...');
    
    // Check if the directory exists
    try {
      await fs.access(this.testDir);
    } catch (error) {
      throw new Error(`Test directory not found: ${this.testDir}`);
    }
    
    // Check for required files
    const requiredFiles = [
      'package.json',
      'README.md',
      'src/App.js',
      'public/index.html'
    ];
    
    for (const file of requiredFiles) {
      const filePath = path.join(this.testDir, file);
      try {
        await fs.access(filePath);
        console.log(`✅ Found: ${file}`);
      } catch (error) {
        console.warn(`⚠️  Missing: ${file}`);
      }
    }
    
    // Verify package.json
    try {
      const pkgPath = path.join(this.testDir, 'package.json');
      const pkgContent = await fs.readFile(pkgPath, 'utf-8');
      const pkg = JSON.parse(pkgContent);
      
      console.log('\n📦 Package Info:');
      console.log(`- Name: ${pkg.name || 'Not specified'}`);
      console.log(`- Version: ${pkg.version || 'Not specified'}`);
      console.log(`- Scripts: ${Object.keys(pkg.scripts || {}).join(', ') || 'None'}`);
      
      if (!pkg.name || !pkg.version) {
        console.warn('⚠️  package.json is missing required fields');
      }
    } catch (error) {
      console.error('Error reading package.json:', error.message);
    }
  }

  async cleanup() {
    console.log('\n🧹 Cleaning up test files...');
    try {
      await fs.rm(this.testDir, { recursive: true, force: true });
      console.log('✅ Cleanup complete');
    } catch (error) {
      console.warn('⚠️  Failed to clean up test files:', error.message);
    }
  }
}

// Run the tests
const tester = new AutomationTester();
tester.run().catch(console.error);
