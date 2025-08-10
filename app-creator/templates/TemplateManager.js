import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs/promises';

class TemplateManager {
  constructor() {
    this.templates = [];
    this.initialized = false;
  }

  /**
   * Initialize templates
   */
  async init() {
    if (this.initialized) return;
    
    try {
      // Load built-in templates
      const templatesDir = path.join(
        path.dirname(fileURLToPath(import.meta.url)),
        '..',
        'templates'
      );
      
      const templateDirs = await fs.readdir(templatesDir, { withFileTypes: true });
      
      for (const dir of templateDirs) {
        if (dir.isDirectory()) {
          const templatePath = path.join(templatesDir, dir.name, 'template.json');
          try {
            const templateData = await fs.readFile(templatePath, 'utf-8');
            const template = JSON.parse(templateData);
            this.templates.push({
              ...template,
              path: path.dirname(templatePath)
            });
          } catch (error) {
            console.warn(`Skipping invalid template in ${dir.name}:`, error.message);
          }
        }
      }
      
      this.initialized = true;
    } catch (error) {
      console.error('Error initializing templates:', error);
      throw new Error('Failed to initialize template manager');
    }
  }

  /**
   * Find the best matching template for the given requirements
   * @param {Object} requirements - Parsed requirements
   * @returns {Object} - Best matching template
   */
  findBestMatch(requirements) {
    if (!this.initialized) {
      throw new Error('Template manager not initialized');
    }

    // Simple matching logic - can be enhanced with more sophisticated scoring
    const appType = requirements.app_type?.toLowerCase() || 'web';
    
    // First try exact match
    let template = this.templates.find(t => 
      t.types.some(type => type.toLowerCase() === appType)
    );

    // Then try partial match
    if (!template) {
      template = this.templates.find(t => 
        t.types.some(type => 
          appType.includes(type.toLowerCase()) || 
          type.toLowerCase().includes(appType)
        )
      );
    }

    // Fallback to default template
    if (!template) {
      template = this.templates.find(t => t.isDefault) || this.templates[0];
    }

    if (!template) {
      throw new Error('No suitable template found');
    }

    return template;
  }

  /**
   * Get template files
   * @param {string} templateName - Name of the template
   * @returns {Promise<Array>} - Array of template files
   */
  async getTemplateFiles(templateName) {
    const template = this.templates.find(t => t.name === templateName);
    if (!template) {
      throw new Error(`Template not found: ${templateName}`);
    }

    const files = [];
    await this._readDirectoryRecursive(template.path, files, template.path);
    return files;
  }

  /**
   * Read directory recursively
   * @private
   */
  async _readDirectoryRecursive(dir, fileList = [], basePath) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relativePath = path.relative(basePath, fullPath);
      
      if (entry.isDirectory()) {
        await this._readDirectoryRecursive(fullPath, fileList, basePath);
      } else if (entry.isFile() && !relativePath.includes('template.json')) {
        const content = await fs.readFile(fullPath, 'utf-8');
        fileList.push({
          path: relativePath,
          content
        });
      }
    }
    
    return fileList;
  }
}

export { TemplateManager };
