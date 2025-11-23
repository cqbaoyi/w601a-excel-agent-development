# Excel Agent

An intelligent Excel analysis agent that understands natural language questions and automatically generates Python code to perform data analysis.

## Features

- Natural language processing (Chinese and English)
- Automatic Excel file selection using knowledge base
- Python code generation for data analysis
- Real-time streaming with Server-Sent Events (SSE)
- Voice input support via WebSocket
- Interactive graph generation (Plotly HTML charts)
- Column traceability tracking
- Excel preprocessing with LLM-based table reconstruction

## Project Structure

```
w601a-excel-agent-development/
├── app/                    # Backend application
│   ├── main.py            # FastAPI app with endpoints
│   ├── codegen/           # Code generation
│   ├── execution/         # Code execution
│   ├── nlp/              # Natural language processing
│   ├── preprocessing/     # Excel file preprocessing
│   └── traceability/     # Column tracking
├── frontend/             # React frontend
│   └── src/
│       ├── App.jsx       # Main React component
│       ├── components/   # React components
│       └── services/     # API and WebSocket clients
├── sheets/               # Excel files directory
├── output/               # Generated HTML charts
├── reconstructed_tables/ # Reconstructed Excel files (git-ignored)
└── requirements.txt      # Python dependencies
```

## Installation

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
   - "Show me a chart of sales over time"
4. The system will automatically:
   - Parse your question
   - Select the appropriate Excel file
   - Generate Python analysis code
   - Execute the code
   - Display results, graphs, and column traceability

### Voice Input

1. Click "Start Voice Input" button
2. Speak your question (supports Chinese and English)
3. The system will automatically transcribe and analyze

## API Endpoints

- `GET /api/files` - List available Excel files
- `POST /api/analyze?question=<question>` - Analyze a question (non-streaming)
- `GET /api/analyze/stream?question=<question>` - Stream analysis results via SSE
- `WebSocket /ws/voice` - Voice input transcriptions

## How It Works

1. **File Selection**: Uses a knowledge base of file summaries to quickly identify relevant Excel files
2. **Excel Preprocessing**: Reconstructs complex Excel structures (merged cells, multi-level headers) into clean 2D tables
3. **Code Generation**: Uses OpenAI to generate Python pandas code based on the question and table schema
4. **Code Execution**: Safely executes generated code in a Jupyter kernel
5. **Graph Detection**: Parses generated code to identify and display HTML charts
6. **Column Tracking**: Identifies which Excel columns were used in the analysis

## Technical Details

- **Backend**: FastAPI with WebSocket and SSE support
- **Frontend**: React with Vite
- **AI**: OpenAI API for natural language understanding and code generation
- **Execution**: Jupyter kernel for safe Python code execution
- **Charts**: Plotly for interactive HTML visualizations
