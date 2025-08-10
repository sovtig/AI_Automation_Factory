import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs/promises';
import { LMStudioClient } from '@lmstudio/sdk';
import { LMSTUDIO_CONFIG } from '../config/lmstudio.config.js';

class CodeGenerator {
  constructor() {
    this.config = LMSTUDIO_CONFIG;
    this.client = new LMStudioClient({
      host: this.config.server.host,
      port: this.config.server.port,
      timeout: this.config.server.timeout
    });
  }

  /**
   * Generate application code based on template and requirements
   * @param {Object} template - Selected template
   * @param {Object} requirements - Parsed requirements
   * @returns {Promise<Array>} - Generated files with content
   */
  async generate(template, requirements) {
    try {
      console.log(`🚀 Generating ${requirements.app_name || 'app'} using ${template.name} template...`);
      
      // Get template files
      const templateFiles = await this.getTemplateFiles(template);
      
      // Process each file with the requirements
      const generatedFiles = [];
      
      for (const file of templateFiles) {
        const processedContent = await this.processFile(file.content, template, requirements);
        generatedFiles.push({
          path: this.processPath(file.path, requirements),
          content: processedContent
        });
      }
      
      // Generate additional files based on requirements
      const additionalFiles = await this.generateAdditionalFiles(template, requirements);
      generatedFiles.push(...additionalFiles);
      
      return generatedFiles;
    } catch (error) {
      console.error('Error generating code:', error);
      throw new Error('Failed to generate application code');
    }
  }

  /**
   * Process a single template file with requirements
   * @private
   */
  async processFile(content, template, requirements) {
    // Simple variable replacement
    let processed = content
      .replace(/{{APP_NAME}}/g, requirements.app_name || 'MyApp')
      .replace(/{{APP_DESCRIPTION}}/g, requirements.description || 'Generated with Cascade App Creator')
      .replace(/{{AUTHOR}}/g, requirements.author || 'Cascade User');

    // Use AI for more complex transformations if needed
    if (content.includes('{{AI_GENERATED}}')) {
      processed = await this.generateWithAI(content, requirements);
    }

    return processed;
  }

  /**
   * Process file paths with requirements
   * @private
   */
  processPath(filePath, requirements) {
    return filePath
      .replace(/{{APP_NAME}}/g, requirements.app_name?.toLowerCase().replace(/\s+/g, '-') || 'my-app')
      .replace(/\/templates\//g, '/');
  }

  /**
   * Generate additional files based on requirements
   * @private
   */
  async generateAdditionalFiles(template, requirements) {
    const files = [];
    
    // Generate README.md
    files.push({
      path: 'README.md',
      content: `# ${requirements.app_name || 'My App'}

${requirements.description || 'A new application generated with Cascade App Creator'}

## Features

${this.generateFeatureList(requirements.features || [])}

## Getting Started

1. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`

2. Start development server:
   \`\`\`bash
   ${template.scripts?.dev || 'npm start'}
   \`\`\`

## Building for Production

\`\`\`bash
${template.scripts?.build || 'npm run build'}
\`\`\`
`
    });

    return files;
  }

  /**
   * Generate feature list for README
   * @private
   */
  generateFeatureList(features) {
    if (!features || features.length === 0) {
      return '- Feature 1\n- Feature 2\n- Feature 3';
    }
    return features.map(f => `- ${f}`).join('\n');
  }

  /**
   * Use AI to generate content
   * @private
   */
  async generateWithAI(template, requirements) {
    try {
      const model = await this.getFirstAvailableModel();
      const response = await this.client.chat.completions.create({
        model: model,
        messages: [
          {
            role: 'system',
            content: this.config.prompts.codeGeneration
          },
          {
            role: 'user',
            content: `Generate code with these requirements:
            
App Name: ${requirements.app_name || 'MyApp'}
Type: ${requirements.app_type || 'web'}
Framework: ${requirements.framework || 'React'}

Features:
${(requirements.features || []).map(f => `- ${f}`).join('\n')}

Dependencies: ${(requirements.dependencies || []).join(', ')}

Template Context:
${JSON.stringify(template, null, 2)}

Generate clean, well-structured code following best practices for the specified framework.`
          }
        ],
        ...this.config.model.parameters,
        temperature: 0.3 // Slightly higher temperature for creative code generation
      });

      const content = response.choices[0].message.content;
      // Clean up the response if it's wrapped in markdown code blocks
      const codeMatch = content.match(/```(?:\w+)?\n([\s\S]*?)\n```/);
      return codeMatch ? codeMatch[1].trim() : content.trim();
    } catch (error) {
      console.error('AI generation failed:', error.message);
      return '// AI generation failed. Please implement this component manually.';
    }
  }

  async getFirstAvailableModel() {
    const models = await this.client.models.list();
    if (models.data.length === 0) {
      throw new Error('No models available. Please load a model in LM Studio.');
    }
    return models.data[0].id;
  }

  async getTemplateFiles(template) {
    // In a real implementation, this would read files from the template directory
    // For now, we'll return some basic template files
    return [
      {
        path: 'package.json',
        content: `{
  "name": "{{APP_NAME}}",
  "version": "0.1.0",
  "private": true,
  "dependencies": ${JSON.stringify(template.dependencies || {}, null, 2)},
  "devDependencies": ${JSON.stringify(template.devDependencies || {}, null, 2)},
  "scripts": ${JSON.stringify(template.scripts || {}, null, 2)}
}`
      },
      {
        path: 'src/App.js',
        content: `import React from 'react';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Welcome to {{APP_NAME}}</h1>
        <p>{{APP_DESCRIPTION}}</p>
        {{AI_GENERATED}}
      </header>
    </div>
  );
}

export default App;`
      }
    ];
  }
}

export { CodeGenerator };
