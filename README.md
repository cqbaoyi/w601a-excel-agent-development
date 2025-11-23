# Excel Agent Development

An intelligent Excel analysis agent that understands natural language questions and automatically generates Python code to perform data analysis.

## Features

- **Natural Language Processing**: Understands questions in Chinese or English
- **Intelligent File Selection**: 
  - Uses a knowledge base of file summaries for fast, cheap file filtering
  - Automatically selects the appropriate Excel file from the `sheets` directory
  - Summaries are cached to minimize API costs
- **Code Generation**: Generates Python pandas code based on user questions
- **Real-time Streaming**: Uses Server-Sent Events (SSE) for real-time code generation with typewriter effect
- **Voice Input**: Supports voice input via WebSocket using Web Speech API
- **Code Execution**: Safely executes generated code using Jupyter kernel
- **Data Traceability**: Tracks and reports which Excel columns were used in the analysis
- **Excel Preprocessing**: 
  - **Original Files**: Reads and analyzes complex Excel structures (merged cells, multi-level headers) without modifying original files
  - **LLM-Based Reconstruction**: Uses Large Language Model to clean and reconstruct unstructured/semi-structured tables into standard 2D data tables
  - **Temporary Storage**: Reconstructed tables are stored in `reconstructed_tables/` directory (git-ignored) for analysis

## Architecture

- **Backend**: FastAPI with WebSocket and SSE support
- **Frontend**: React with Vite
- **AI**: OpenAI API for natural language understanding and code generation
- **Execution**: Jupyter kernel for safe Python code execution

## Project Structure

```
w601a-excel-agent-development/
├── app/                          # Backend application
│   ├── main.py                  # FastAPI app with endpoints
│   ├── preprocessing/           # Excel file preprocessing
│   ├── nlp/                     # Natural language processing
│   ├── codegen/                 # Code generation
│   ├── execution/               # Code execution
│   └── traceability/            # Column tracking
├── frontend/                    # React frontend
│   ├── src/
│   │   ├── App.jsx             # Main React component
│   │   ├── components/         # React components
│   │   └── services/           # API and WebSocket clients
│   └── package.json
├── sheets/                      # Excel files directory
├── reconstructed_tables/        # Reconstructed Excel files (git-ignored)
├── file_summaries.json          # File summaries cache with knowledge base (git-ignored)
├── requirements.txt             # Python dependencies
└── README.md
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
SHEETS_DIR=sheets
```

3. Start the backend server:
```bash
python -m app.main
```

Or using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Place your Excel files in the `sheets/` directory
2. Open the frontend application in your browser
3. Enter a question in natural language (Chinese or English), for example:
   - "Analyze sales trends in different regions"
   - "计算不同地区的销售趋势"
   - "Show me the top 10 products by sales"
4. The system will:
   - Parse your question
   - Select the appropriate Excel file
   - Generate Python analysis code
   - Execute the code
   - Display results and column traceability

### Voice Input

1. Click "Start Voice Input" button
2. Speak your question (supports Chinese and English)
3. The system will automatically transcribe and analyze

## API Endpoints

### GET `/api/files`
List all available Excel files in the sheets directory.

### POST `/api/analyze?question=<question>`
Analyze a question (non-streaming).

### GET `/api/analyze/stream?question=<question>`
Stream analysis results via Server-Sent Events (SSE).

### WebSocket `/ws/voice`
WebSocket endpoint for voice input transcriptions.

## Technical Details

### Excel Preprocessing

The system handles complex Excel files with a two-stage process:

1. **Original File Analysis** (Read-only):
   - Identifies merged cells and multi-level headers
   - Analyzes table structure without modifying the original file
   - Files in `sheets/` directory remain untouched

2. **LLM-Based Reconstruction**:
   - Uses Large Language Model to understand table structure
   - Cleans and reconstructs unstructured/semi-structured data
   - Converts to standard two-dimensional data tables
   - Ensures data format consistency and accuracy

3. **Temporary Storage**:
   - Reconstructed tables are written to `reconstructed_tables/` directory
   - This directory is git-ignored
   - Reconstructed files are reused if they already exist (cached)
   - Old reconstructed files can be automatically cleaned up

The original Excel files are never modified, ensuring data integrity.

### Knowledge Base for File Selection

The system uses a cost-effective knowledge base approach for intelligent file selection:

1. **File Summarization**:
   - Each Excel file is analyzed once using OpenAI (gpt-4o-mini - cheap model)
   - Generates concise 2-3 sentence summaries describing content and purpose
   - Summaries are cached in `file_summaries.json` (git-ignored)

2. **Knowledge Base Search**:
   - All file summaries are stored in `file_summaries.json` with keyword indexing
   - Uses keyword-based indexing for fast retrieval (no API calls needed)
   - Built-in search functionality to find relevant files by query

3. **Smart Filtering**:
   - When a user asks a question, the knowledge base quickly filters relevant files
   - Only top 5 most relevant files are sent to OpenAI for final selection
   - Reduces API costs by filtering before expensive operations

4. **Automatic Updates**:
   - Knowledge base is automatically built/updated on startup
   - Only new or modified files trigger summary regeneration
   - Cached summaries are reused to minimize costs
   - Index is automatically rebuilt when summaries are added/updated

### Code Generation Rules

Generated code follows strict pandas conventions:
- Proper data type conversions
- Error handling
- Defensive programming
- Clear output formatting

### Security

- File path validation
- Safe code execution in isolated kernel
- Input sanitization

## Development

### Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Write docstrings for all functions
- Follow React best practices for frontend

### Testing

Test the system with various Excel file structures and question types to ensure robustness.

## License

[Add your license here]
