"""
AI Factory Integration Module

Provides integration with the AI Factory for processing automation tasks
using the GLASP RAG system and AI models.
"""
import os
import json
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from loguru import logger

from models.ai_models import AIModel, AIModelClient, AIModelFactory
from models.database import database

class TaskType(str, Enum):
    """Supported task types for AI Factory processing."""
    INFO_EXTRACTION = "info_extraction"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    QA = "qa"
    CODE_GENERATION = "code_generation"

@dataclass
class AIFactoryRequest:
    """Request payload for AI Factory processing."""
    task_type: TaskType
    content: Union[str, Dict[str, Any]]
    model: str = "gpt-4-turbo"
    parameters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class AIFactoryResponse:
    """Response from AI Factory processing."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None

class AIFactoryClient:
    """Client for interacting with the AI Factory service."""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        """Initialize the AI Factory client.
        
        Args:
            base_url: Base URL of the AI Factory service. Defaults to environment variable AI_FACTORY_URL.
            api_key: API key for authentication. Defaults to environment variable AI_FACTORY_API_KEY.
        """
        self.base_url = base_url or os.getenv("AI_FACTORY_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("AI_FACTORY_API_KEY")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            } if self.api_key else {"Content-Type": "application/json"}
        )
        self.logger = logger.bind(component="AIFactoryClient")
    
    async def process_task(self, request: AIFactoryRequest) -> AIFactoryResponse:
        """Process a task using the AI Factory.
        
        Args:
            request: The AIFactoryRequest containing task details.
            
        Returns:
            AIFactoryResponse with the processing results.
        """
        try:
            self.logger.info(f"Processing {request.task_type} task with model {request.model}")
            
            # Prepare payload
            payload = {
                "task_type": request.task_type.value,
                "content": request.content,
                "model": request.model,
                "parameters": request.parameters or {},
                "context": request.context or {},
                "metadata": request.metadata or {}
            }
            
            # Make API request
            response = await self.client.post(
                "/api/tasks",
                json=payload,
                timeout=60.0  # 60 second timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            return AIFactoryResponse(
                success=True,
                result=result.get("result"),
                metadata=result.get("metadata"),
                processing_time=result.get("processing_time")
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error: {e.response.status_code} - {e.response.text}"
            self.logger.error(error_msg)
            return AIFactoryResponse(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Error processing task: {str(e)}"
            self.logger.error(error_msg)
            return AIFactoryResponse(success=False, error=error_msg)
    
    async def get_rag_context(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant context using the GLASP RAG system.
        
        Args:
            query: The search query.
            top_k: Number of relevant documents to retrieve.
            
        Returns:
            List of relevant documents with scores.
        """
        try:
            response = await self.client.get(
                "/api/rag/retrieve",
                params={"query": query, "top_k": top_k}
            )
            response.raise_for_status()
            return response.json().get("results", [])
            
        except Exception as e:
            self.logger.error(f"Error retrieving RAG context: {str(e)}")
            return []
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

class GLASPRAGIntegration:
    """Integration with GLASP RAG system for retrieval-augmented generation."""
    
    def __init__(self, ai_factory_client: AIFactoryClient):
        """Initialize the GLASP RAG integration.
        
        Args:
            ai_factory_client: An instance of AIFactoryClient.
        """
        self.client = ai_factory_client
        self.logger = logger.bind(component="GLASPRAG")
    
    async def generate_with_rag(
        self,
        prompt: str,
        context_queries: List[str],
        model: str = "gpt-4-turbo",
        max_tokens: int = 2000,
        temperature: float = 0.7,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """Generate text using RAG-augmented generation.
        
        Args:
            prompt: The input prompt for generation.
            context_queries: List of queries to retrieve relevant context.
            model: The AI model to use for generation.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature.
            top_k: Number of relevant documents to retrieve per query.
            
        Returns:
            Dictionary containing the generated text and metadata.
        """
        try:
            # Retrieve relevant context
            context_docs = []
            for query in context_queries:
                context = await self.client.get_rag_context(query, top_k=top_k)
                context_docs.extend(context)
            
            # Prepare the prompt with context
            context_str = "\n\n".join(
                f"[Document {i+1}]\n{doc['content']}"
                for i, doc in enumerate(context_docs)
            )
            
            enhanced_prompt = f"""Use the following context to answer the question or complete the task.
            If the context doesn't contain relevant information, use your general knowledge.
            
            Context:
            {context}
            
            Task: {prompt}
            """.format(context=context_str, prompt=prompt)
            
            # Generate response using the AI model
            request = AIFactoryRequest(
                task_type=TaskType.QA,
                content={"prompt": enhanced_prompt},
                model=model,
                parameters={
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            
            response = await self.client.process_task(request)
            
            if response.success:
                return {
                    "success": True,
                    "generated_text": response.result.get("text"),
                    "context_docs": context_docs,
                    "metadata": {
                        "model": model,
                        "context_queries": context_queries,
                        "context_docs_count": len(context_docs),
                        "processing_time": response.processing_time
                    }
                }
            else:
                return {
                    "success": False,
                    "error": response.error,
                    "metadata": {"model": model}
                }
                
        except Exception as e:
            error_msg = f"Error in RAG generation: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "metadata": {"model": model}
            }

# Example usage
async def example_usage():
    """Example of using the AI Factory integration."""
    client = AIFactoryClient()
    rag = GLASPRAGIntegration(client)
    
    try:
        # Example RAG generation
        result = await rag.generate_with_rag(
            prompt="What are the latest advancements in AI automation?",
            context_queries=["AI automation", "recent AI advancements"],
            model="gpt-4-turbo"
        )
        
        if result["success"]:
            print("Generated text:", result["generated_text"])
            print(f"Used {len(result['context_docs'])} context documents")
        else:
            print("Error:", result.get("error", "Unknown error"))
            
    finally:
        await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
