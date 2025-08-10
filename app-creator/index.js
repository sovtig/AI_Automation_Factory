import { AppCreator } from './core/AppCreator.js';
import { NLPParser } from './parsers/NLPParser.js';
import { TemplateManager } from './templates/TemplateManager.js';
import { CodeGenerator } from './generators/CodeGenerator.js';

class CascadeAppCreator {
  constructor() {
    this.parser = new NLPParser();
    this.templateManager = new TemplateManager();
    this.generator = new CodeGenerator();
  }

  /**
   * Create an app based on natural language description
   * @param {string} description - Natural language description of the app
   * @returns {Promise<Object>} - Result containing app files and metadata
   */
  async createApp(description) {
    try {
      console.log('🔍 Analyzing your request...');
      
      // Parse natural language to structured requirements
      const requirements = await this.parser.parse(description);
      
      // Find matching templates
      const template = this.templateManager.findBestMatch(requirements);
      
      // Generate code based on template and requirements
      const appFiles = await this.generator.generate(template, requirements);
      
      console.log('✅ App created successfully!');
      return {
        success: true,
        files: appFiles,
        requirements,
        template: template.name
      };
    } catch (error) {
      console.error('❌ Error creating app:', error.message);
      return {
        success: false,
        error: error.message
      };
    }
  }
}

export { CascadeAppCreator };
