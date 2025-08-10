"""
AI Model Integration for AI Automation Factory

Provides a unified interface for interacting with various AI models.
"""
from enum import Enum
from typing import List, Dict, Optional, Union, AsyncGenerator
from dataclasses import dataclass
import openai
import os
from loguru import logger

class ModelProvider(str, Enum):
    """Supported AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    LOCAL = "local"

class AIModel(str, Enum):
    """Supported AI models with their providers."""
    # OpenAI models
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    GPT35_TURBO = "gpt-3.5-turbo"
    
    # Anthropic models
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    
    # Cohere models
    COMMAND_R = "command-r"
    
    # Local models
    LLAMA3_8B = "llama3-8b"

@dataclass
class GenerationConfig:
    """Configuration for AI model generation."""
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    stream: bool = False

class AIModelClient:
    """Base class for AI model clients."""
    
    def __init__(self, model: AIModel, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
        self.logger = logger.bind(model=model.value)
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[GenerationConfig] = None
    ) -> Dict[str, Any]:
        """Generate a response from the AI model."""
        config = config or GenerationConfig()
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model.value,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                stream=config.stream
            )
            
            if config.stream:
                return await self._handle_streaming_response(response)
            return self._format_response(response)
            
        except Exception as e:
            self.logger.error(f"Generation error: {str(e)}")
            raise
    
    async def _handle_streaming_response(self, response):
        """Handle streaming responses."""
        full_content = ""
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_content += content
                yield {
                    'content': content,
                    'finished': False,
                    'metadata': {'model': self.model.value}
                }
        
        yield {
            'content': full_content,
            'finished': True,
            'metadata': {'model': self.model.value}
        }
    
    def _format_response(self, response):
        """Format the response from the API."""
        return {
            'content': response.choices[0].message.content,
            'finished': True,
            'metadata': {
                'model': self.model.value,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
        }

class AIModelFactory:
    """Factory for creating AI model clients."""
    
    @staticmethod
    def create_client(model: Union[str, AIModel], api_key: Optional[str] = None):
        """Create an AI model client."""
        if isinstance(model, str):
            model = AIModel(model.upper())
        
        if model in [AIModel.GPT4, AIModel.GPT4_TURBO, AIModel.GPT35_TURBO]:
            return AIModelClient(model, api_key)
        else:
            raise ValueError(f"Unsupported model: {model}")

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_generation():
        client = AIModelFactory.create_client("gpt-4-turbo")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a short story about AI."}
        ]
        
        # Non-streaming
        response = await client.generate(messages)
        print("Non-streaming response:", response['content'])
        
        # Streaming
        print("\nStreaming response:")
        config = GenerationConfig(stream=True, temperature=0.8)
        async for chunk in client.generate(messages, config):
            if not chunk['finished']:
                print(chunk['content'], end="", flush=True)
    
    asyncio.run(test_generation())
