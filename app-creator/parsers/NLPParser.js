import { LMStudioClient } from '@lmstudio/sdk';
import { LMSTUDIO_CONFIG } from '../config/lmstudio.config.js';

class NLPParser {
  constructor() {
    this.config = LMSTUDIO_CONFIG;
    this.client = new LMStudioClient({
      host: this.config.server.host,
      port: this.config.server.port,
      timeout: this.config.server.timeout
    });
  }

  /**
   * Parse natural language description into structured requirements
   * @param {string} description - Natural language description
   * @returns {Promise<Object>} - Structured requirements
   */
  async parse(description) {
    try {
      const model = await this.getFirstAvailableModel();
      const response = await this.client.chat.completions.create({
        model: model,
        messages: [
          {
            role: 'system',
            content: this.config.prompts.requirementsExtraction
          },
          {
            role: 'user',
            content: `Convert this app description into structured requirements. Include all mentioned features, frameworks, and preferences.\n\nDescription: ${description}`
          }
        ],
        ...this.config.model.parameters,
        response_format: { type: 'json_object' }
      });

      const content = response.choices[0].message.content;
      // Extract JSON from markdown code block if present
      const jsonMatch = content.match(/```(?:json)?\n([\s\S]*?)\n```/);
      const jsonString = jsonMatch ? jsonMatch[1] : content;
      
      return JSON.parse(jsonString);
    } catch (error) {
      console.error('Error parsing requirements:', error);
      throw new Error('Failed to parse app requirements. Please try again with more specific details.');
    }
  }

  async getFirstAvailableModel() {
    const models = await this.client.models.list();
    if (models.data.length === 0) {
      throw new Error('No models available. Please load a model in LM Studio.');
    }
    return models.data[0].id;
  }
}

export { NLPParser };
