# AI Factory Integration Module

## Overview
This module provides PowerShell integration with the AI Factory and LM Studio's local LLM server, enabling powerful AI automation capabilities in your PowerShell workflows.

## Features

- **Seamless Integration**: Connect to LM Studio's local API server
- **High Performance**: Optimized for speed with caching and parallel processing
- **Robust Error Handling**: Comprehensive error handling and retry mechanisms
- **Multiple AI Tasks**: Support for text generation, chat completion, summarization, and Q&A
- **Extensible**: Easy to extend with new AI models and task types

## Prerequisites

- PowerShell 7.0 or later
- LM Studio running with API server enabled
- Required PowerShell modules:
  - PSSQLite (version 1.1.0 or later)

## Installation

1. Clone this repository
2. Import the module in your PowerShell session:

```powershell
# Import the module
Import-Module .\ai_factory.psm1 -Force

# Set your LM Studio API endpoint (if different from default)
$script:ModuleConfig.BaseUri = 'http://localhost:1234/v1'
```

## Usage

### Basic Text Generation

```powershell
$response = Invoke-AITextGeneration -Prompt "Write a haiku about artificial intelligence"
$response.GeneratedText
```

### Chat Completion

```powershell
$messages = @(
    @{ role = "system"; content = "You are a helpful assistant." },
    @{ role = "user"; content = "What's the weather like today?" }
)

$response = Invoke-AIChatCompletion -Messages $messages
$response.choices[0].message.content
```

### Text Summarization

```powershell
$article = "Long article text goes here..."
$summary = Invoke-AISummarization -Text $article -MaxSentences 3 -BulletPoints
$summary.GeneratedText
```

### Question Answering with Context

```powershell
$context = "The AI Factory is a powerful automation framework..."
$question = "What are the main features of the AI Factory?"

$answer = Invoke-AIQuestionAnswering -Question $question -Context $context
$answer.choices[0].message.content
```

## Running the Demo

To see the module in action with example use cases:

```powershell
.\Automate-AITasks.ps1
```

## Configuration

You can customize the module's behavior by modifying the `$script:ModuleConfig` hashtable:

```powershell
# Module configuration
$script:ModuleConfig = @{
    BaseUri = 'http://localhost:1234/v1'  # LM Studio API endpoint
    TimeoutSec = 45                       # Request timeout in seconds
    RetryCount = 3                        # Number of retry attempts
    RetryDelaySec = 2                     # Delay between retries in seconds
    EnableLogging = $true                 # Enable/disable logging
    LogPath = 'ai_factory.log'            # Path to log file
}
```

## Performance Monitoring

Track API performance metrics:

```powershell
# Get performance metrics
$metrics = Get-AIFactoryMetrics
$metrics | Format-List

# Sample output:
# TotalRequests     : 42
# FailedRequests    : 2
# SuccessRate       : 95.24
# AverageResponseMs : 1250.5
# LastError         : 
# Timestamp         : 2025-08-09T15:30:45.1234567-04:00
```

## Error Handling

The module includes comprehensive error handling and logging. Check the log file for detailed error information:

```powershell
# View the last error
$script:PerformanceMetrics.LastError

# View the log file
Get-Content -Path $script:ModuleConfig.LogPath -Tail 20
```

## Best Practices

1. **Batch Requests**: When making multiple API calls, use batching where possible
2. **Error Handling**: Always implement try/catch blocks around API calls
3. **Rate Limiting**: Be mindful of API rate limits and implement appropriate delays
4. **Caching**: Use the built-in caching for frequently accessed data
5. **Logging**: Keep logging enabled for troubleshooting

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure LM Studio is running with the API server enabled
   - Verify the BaseUri in the module configuration
   - Check your firewall settings

2. **Slow Responses**
   - Increase the TimeoutSec value in the module configuration
   - Check your system resources
   - Consider using a smaller model

3. **Authentication Errors**
   - Verify your API key (if required)
   - Check the API endpoint URL

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
