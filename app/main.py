"""FastAPI application with WebSocket and SSE endpoints."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse

from app.codegen.code_generator import CodeGenerator
from app.execution.code_executor import CodeExecutor
from app.nlp.intent_parser import IntentParser
from app.preprocessing.schema_extractor import SchemaExtractor
from app.preprocessing.excel_processor import ExcelProcessor
from app.traceability.column_tracker import ColumnTracker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Excel Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
)

# Initialize components
sheets_dir = os.getenv("SHEETS_DIR", "sheets")
intent_parser = IntentParser(openai_client, sheets_dir)
code_generator = CodeGenerator(openai_client)
code_executor = CodeExecutor()
column_tracker = ColumnTracker()
excel_processor = ExcelProcessor(openai_client)
schema_extractor = SchemaExtractor()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Excel Agent API", "version": "1.0.0"}


@app.get("/api/files")
async def list_files():
    """
    List available Excel files in the sheets directory.
    
    Returns:
        List of file information
    """
    try:
        sheets_path = Path(sheets_dir)
        if not sheets_path.exists():
            return JSONResponse(
                status_code=404,
                content={"error": f"Sheets directory not found: {sheets_dir}"}
            )
        
        excel_files = list(sheets_path.glob("*.xlsx")) + list(sheets_path.glob("*.xls"))
        
        files_info = []
        for file_path in excel_files:
            try:
                import pandas as pd
                df = pd.read_excel(file_path, sheet_name=0, nrows=1)
                files_info.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "columns": list(df.columns),
                    "size": file_path.stat().st_size
                })
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                files_info.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "columns": [],
                    "size": file_path.stat().st_size,
                    "error": str(e)
                })
        
        return {"files": files_info}
        
    except Exception as e:
        logger.error(f"Error listing files: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Error listing files: {str(e)}"}
        )


@app.post("/api/analyze")
async def analyze(question: str = Query(..., description="User's question")):
    """
    Analyze Excel data based on natural language question (non-streaming).
    
    Args:
        question: User's natural language question
        
    Returns:
        Analysis results with code, output, and column traceability
    """
    try:
        # Step 1: Parse intent and select original file
        intent_info = intent_parser.parse_intent(question)
        original_file_path = intent_info["target_file"]
        
        # Step 2: Get or create reconstructed file
        logger.info(f"Processing original file: {original_file_path}")
        reconstructed_file_path = excel_processor.get_reconstructed_path(original_file_path)
        
        if not reconstructed_file_path:
            logger.info("Creating reconstructed file...")
            reconstructed_file_path = excel_processor.process_excel_file(original_file_path)
        else:
            logger.info(f"Using existing reconstructed file: {reconstructed_file_path}")
        
        # Step 2.5: Extract schema from reconstructed file
        logger.info("Extracting schema from reconstructed file...")
        schema = schema_extractor.extract_schema(reconstructed_file_path)
        
        # Step 3: Generate code (use reconstructed file and schema)
        code = code_generator.generate_code(question, reconstructed_file_path, intent_info, schema)
        
        # Step 4: Execute code (use reconstructed file)
        execution_result = code_executor.execute_code(code, reconstructed_file_path)
        
        # Step 5: Track columns (use reconstructed file)
        used_columns = column_tracker.extract_columns_from_code(code, reconstructed_file_path)
        
        return {
            "question": question,
            "intent": intent_info.get("intent"),
            "target_file": intent_info.get("file_name"),
            "reconstructed_file": reconstructed_file_path,
            "code": code,
            "output": execution_result["output"],
            "error": execution_result.get("error"),
            "success": execution_result["success"],
            "columns_used": used_columns,
            "original_file": intent_info.get("file_name", os.path.basename(original_file_path))
        }
        
    except Exception as e:
        logger.error(f"Error in analysis: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Analysis failed: {str(e)}"}
        )


@app.get("/api/analyze/stream")
async def stream_analysis(
    question: str = Query(..., description="User's question")
):
    """
    Stream code generation and analysis via SSE.
    
    Args:
        question: User's natural language question
        
    Returns:
        SSE stream with code chunks and results
    """
    async def generate():
        try:
            # Step 1: Parse intent
            yield {
                "type": "status",
                "data": {"message": "Parsing question and selecting file..."}
            }
            
            intent_info = intent_parser.parse_intent(question)
            original_file_path = intent_info["target_file"]
            
            yield {
                "type": "file_selected",
                "data": {
                    "file_name": intent_info.get("file_name"),
                    "intent": intent_info.get("intent"),
                    "columns": intent_info.get("required_columns", [])
                }
            }
            
            # Step 1.5: Get or create reconstructed file
            yield {
                "type": "status",
                "data": {"message": "Reconstructing Excel table..."}
            }
            
            reconstructed_file_path = excel_processor.get_reconstructed_path(original_file_path)
            if not reconstructed_file_path:
                reconstructed_file_path = excel_processor.process_excel_file(original_file_path)
            
            # Step 1.6: Extract schema from reconstructed file
            yield {
                "type": "status",
                "data": {"message": "Extracting table schema..."}
            }
            
            schema = schema_extractor.extract_schema(reconstructed_file_path)
            
            # Step 2: Stream code generation
            yield {
                "type": "status",
                "data": {"message": "Generating analysis code..."}
            }
            
            accumulated_code = ""
            async for chunk in code_generator.generate_code_stream(question, reconstructed_file_path, intent_info, schema):
                accumulated_code += chunk
                yield {
                    "type": "code_chunk",
                    "data": {"chunk": chunk}
                }
            
            # Step 3: Execute code
            yield {
                "type": "status",
                "data": {"message": "Executing code..."}
            }
            
            execution_result = code_executor.execute_code(accumulated_code, reconstructed_file_path)
            
            yield {
                "type": "execution_result",
                "data": {
                    "output": execution_result["output"],
                    "error": execution_result.get("error"),
                    "success": execution_result["success"]
                }
            }
            
            # Step 4: Track columns
            used_columns = column_tracker.extract_columns_from_code(accumulated_code, reconstructed_file_path)
            
            yield {
                "type": "column_traceability",
                "data": {
                    "columns_used": used_columns,
                    "original_file": intent_info.get("file_name", os.path.basename(original_file_path))
                }
            }
            
            yield {
                "type": "complete",
                "data": {"message": "Analysis complete"}
            }
            
        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            yield {
                "type": "error",
                "data": {"error": str(e)}
            }
    
    async def event_generator():
        try:
            async for event in generate():
                # Include event type in data for frontend compatibility
                event_data = event["data"].copy()
                event_data["type"] = event["type"]
                yield {
                    "event": event["type"],
                    "data": json.dumps(event_data, ensure_ascii=False)
                }
        finally:
            # Ensure connection is properly closed after streaming completes
            logger.info("SSE stream completed, connection closing")
    
    return EventSourceResponse(event_generator())


@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    """
    WebSocket endpoint for receiving voice transcriptions.
    
    When a transcription is received, it triggers the analysis pipeline.
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Receive voice transcription
            data = await websocket.receive_text()
            transcription_data = json.loads(data)
            question = transcription_data.get("text", "").strip()
            
            # Validate question is meaningful
            if not question or len(question) < 3:
                await websocket.send_json({
                    "type": "error",
                    "error": "No valid question received. Please speak clearly or try again."
                })
                continue
            
            logger.info(f"Received voice transcription: {question}")
            
            # Send acknowledgment
            await websocket.send_json({
                "status": "received",
                "question": question
            })
            
            try:
                # Parse intent
                intent_info = intent_parser.parse_intent(question)
                original_file_path = intent_info["target_file"]
                
                await websocket.send_json({
                    "status": "file_selected",
                    "file_name": intent_info.get("file_name"),
                    "intent": intent_info.get("intent")
                })
                
                # Get or create reconstructed file
                await websocket.send_json({
                    "type": "status",
                    "message": "Reconstructing Excel table..."
                })
                
                reconstructed_file_path = excel_processor.get_reconstructed_path(original_file_path)
                if not reconstructed_file_path:
                    reconstructed_file_path = excel_processor.process_excel_file(original_file_path)
                
                # Extract schema from reconstructed file
                await websocket.send_json({
                    "type": "status",
                    "message": "Extracting table schema..."
                })
                
                schema = schema_extractor.extract_schema(reconstructed_file_path)
                
                # Generate code (non-streaming for WebSocket)
                code = code_generator.generate_code(question, reconstructed_file_path, intent_info, schema)
                
                # Send code in chunks for typewriter effect
                chunk_size = 50
                for i in range(0, len(code), chunk_size):
                    chunk = code[i:i + chunk_size]
                    await websocket.send_json({
                        "type": "code_chunk",
                        "chunk": chunk
                    })
                
                # Execute code
                execution_result = code_executor.execute_code(code, reconstructed_file_path)
                
                await websocket.send_json({
                    "type": "execution_result",
                    "output": execution_result["output"],
                    "error": execution_result.get("error"),
                    "success": execution_result["success"]
                })
                
                # Track columns
                used_columns = column_tracker.extract_columns_from_code(code, reconstructed_file_path)
                
                await websocket.send_json({
                    "type": "column_traceability",
                    "columns_used": used_columns,
                    "original_file": intent_info.get("file_name", os.path.basename(original_file_path))
                })
                
                await websocket.send_json({
                    "type": "complete",
                    "message": "Analysis complete"
                })
                
            except Exception as e:
                logger.error(f"Error processing voice input: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

