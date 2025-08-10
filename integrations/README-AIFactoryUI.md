# AI Factory UI

A modern Windows Forms application that provides a user-friendly interface for interacting with the AI Factory module, featuring conversation history and Retrieval-Augmented Generation (RAG) integration.

## Features

- **Conversation Management**: Create, view, and delete conversation histories
- **Rich Text Chat**: Color-coded messages for users and AI responses
- **RAG Integration**: View context and sources used for AI responses
- **Export Conversations**: Save conversations as text or markdown files
- **Responsive UI**: Resizable panels and modern controls

## Prerequisites

- Windows 10/11
- PowerShell 5.1 or later
- .NET Framework 4.7.2 or later
- AI Factory PowerShell module and its dependencies

## Installation

1. Ensure you have the AI Factory PowerShell module installed:
   ```powershell
   Import-Module .\ai_factory.psm1 -Force
   ```

2. Make sure all required .NET assemblies are available (they should be included with Windows):
   - System.Windows.Forms
   - System.Drawing
   - System.Windows.Forms.DataVisualization

## Running the Application

To start the AI Factory UI, run the following command in PowerShell:

```powershell
.\AIFactoryUI.ps1
```

## Usage Guide

### Starting a New Conversation
1. Click the "New" button in the conversations panel
2. Enter your message in the input box at the bottom
3. Press Enter or click "Send" to send your message

### Managing Conversations
- **Switch Conversations**: Click on a conversation in the left panel to view its history
- **Delete Conversation**: Select a conversation and click the "Delete" button
- **Export Conversation**: Right-click in the chat area and select "Export Conversation"

### Using RAG Features
- **Enable/Disable RAG**: Use the checkbox in the bottom-right corner to toggle RAG integration
- **View Context**: The right panel shows the RAG context used for the current conversation

### Keyboard Shortcuts
- **Enter**: Send message
- **Ctrl+Enter**: Add a new line in the input box
- **Ctrl+C**: Copy selected text
- **Ctrl+N**: New conversation
- **Delete**: Delete selected conversation

## Troubleshooting

### Common Issues

1. **UI Not Loading**:
   - Ensure all required .NET assemblies are installed
   - Run PowerShell as Administrator
   - Check for error messages in the console

2. **RAG Not Working**:
   - Verify that the RAG service is running and accessible
   - Check network connectivity if using a remote RAG service
   - Review the application logs for errors

3. **Conversations Not Saving**:
   - Ensure the application has write permissions to the conversation storage location
   - Check disk space availability

## Testing

Run the test script to verify all components are working correctly:

```powershell
.\tests\Test-AIFactoryUI.ps1
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with PowerShell and Windows Forms
- Integrates with the AI Factory module for AI capabilities
- Uses RAG for enhanced context-aware responses
