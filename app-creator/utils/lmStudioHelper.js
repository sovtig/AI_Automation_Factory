import { LMStudioClient } from '@lmstudio/sdk';
import { LMSTUDIO_CONFIG } from '../config/lmstudio.config.js';
import { spawn } from 'child_process';
import path from 'path';

class LMStudioHelper {
  constructor() {
    this.config = LMSTUDIO_CONFIG;
    this.client = new LMStudioClient({
      host: this.config.server.host,
      port: this.config.server.port,
      timeout: this.config.server.timeout
    });
    this.lmProcess = null;
  }

  /**
   * Check if LM Studio server is running
   * @returns {Promise<boolean>} - True if server is running
   */
  async isServerRunning() {
    try {
      await this.client.health();
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Start LM Studio application
   * @returns {Promise<boolean>} - True if started successfully
   */
  async startLMStudio() {
    try {
      const lmPath = await this.findLMStudio();
      console.log(`🚀 Starting LM Studio from: ${lmPath}`);
      
      this.lmProcess = spawn(lmPath, [], {
        detached: true,
        stdio: 'ignore'
      });
      
      this.lmProcess.unref();
      return true;
    } catch (error) {
      console.error('Failed to start LM Studio:', error.message);
      return false;
    }
  }

  /**
   * Find LM Studio executable
   * @private
   */
  async findLMStudio() {
    for (const lmPath of this.config.lmStudioPaths || []) {
      try {
        const fullPath = path.normalize(lmPath);
        const { access } = await import('fs/promises');
        await access(fullPath);
        return fullPath;
      } catch (error) {
        // Try next path
      }
    }
    throw new Error('LM Studio not found. Please install it first.');
  }

  /**
   * Wait for LM Studio server to be ready
   * @param {number} timeout - Timeout in milliseconds
   * @returns {Promise<boolean>} - True if server is ready
   */
  async waitForServer(timeout = 60000) {
    const startTime = Date.now();
    const checkInterval = 3000; // 3 seconds
    
    while (Date.now() - startTime < timeout) {
      if (await this.isServerRunning()) {
        console.log('✅ LM Studio server is ready!');
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, checkInterval));
    }
    
    throw new Error('Timed out waiting for LM Studio server to start');
  }

  /**
   * Get the first available model
   * @returns {Promise<string>} - Model ID
   */
  async getFirstAvailableModel() {
    try {
      const models = await this.client.models.list();
      if (models.data.length === 0) {
        throw new Error('No models available. Please load a model in LM Studio.');
      }
      
      // Try to find the default model first
      const defaultModel = models.data.find(m => 
        m.id.includes(this.config.model.default)
      );
      
      return defaultModel ? defaultModel.id : models.data[0].id;
    } catch (error) {
      console.error('Error getting available models:', error.message);
      throw new Error('Failed to get available models. Make sure LM Studio is running with a model loaded.');
    }
  }
}

export const lmStudioHelper = new LMStudioHelper();
