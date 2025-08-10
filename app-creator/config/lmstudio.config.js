// LM Studio Configuration
export const LMSTUDIO_CONFIG = {
  // LM Studio server settings
  server: {
    host: 'localhost',
    port: 1234,
    timeout: 60000, // 1 minute timeout
    healthCheckEndpoint: '/v1/health',
    modelsEndpoint: '/v1/models'
  },
  
  // Default model settings
  model: {
    // Default model to use if not specified
    default: 'mistral-moe-4x7b-dark-multiverse-uncensored-enhanced32-24b',
    
    // Model parameters
    parameters: {
      temperature: 0.2,
      max_tokens: 2000,
      top_p: 0.9,
      frequency_penalty: 0.0,
      presence_penalty: 0.0,
      stop: ['\n', '###']
    }
  },
  
  // System prompts for different tasks
  prompts: {
    requirementsExtraction: `You are an AI that helps convert natural language app descriptions into structured requirements.
Extract the following information:
- app_name: Name of the application
- app_type: Type of application (web, cli, api, desktop, etc.)
- framework: Preferred framework (if mentioned)
- features: List of main features
- dependencies: Any mentioned libraries or dependencies
- ui_preferences: UI/UX preferences if mentioned
Output should be valid JSON.`,
    
    codeGeneration: `You are an expert code generator. Generate high-quality, production-ready code based on the requirements.
Follow these guidelines:
1. Use modern JavaScript/TypeScript best practices
2. Include proper error handling
3. Add helpful comments
4. Keep the code clean and maintainable
5. Follow the specified framework conventions
6. Only return the code, no explanations`
  }
};

export default LMSTUDIO_CONFIG;
