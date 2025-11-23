"""FastAPI application with WebSocket and SSE endpoints."""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse

from app.codegen.code_generator import CodeGenerator
from app.execution.code_executor import CodeExecutor
from app.nlp.intent_parser import IntentParser
from app.preprocessing.schema_extractor import SchemaExtractor
from app.preprocessing.excel_processor import ExcelProcessor
from app.traceability.column_tracker import ColumnTracker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Excel Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
)

sheets_dir = os.getenv("SHEETS_DIR", "sheets")
intent_parser = IntentParser(openai_client, sheets_dir)
code_generator = CodeGenerator(openai_client)
code_executor = CodeExecutor()
column_tracker = ColumnTracker()
excel_processor = ExcelProcessor(openai_client)
schema_extractor = SchemaExtractor()

output_dir = Path(__file__).parent.parent / "output"
output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")


def _prepare_analysis(question: str):
    """Common analysis preparation steps."""
    intent_info = intent_parser.parse_intent(question)
    original_file_path = intent_info["target_file"]
    
    reconstructed_file_path = excel_processor.get_reconstructed_path(original_file_path)
    if not reconstructed_file_path:
        reconstructed_file_path = excel_processor.process_excel_file(original_file_path)
    
    schema = schema_extractor.extract_schema(reconstructed_file_path)
    
    return intent_info, original_file_path, reconstructed_file_path, schema


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Excel Agent API", "version": "1.0.0"}


@app.get("/api/files")
async def list_files():
    """List available Excel files in the sheets directory."""
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
    """Analyze Excel data based on natural language question (non-streaming)."""
    try:
        intent_info, original_file_path, reconstructed_file_path, schema = _prepare_analysis(question)
        
        code = code_generator.generate_code(question, reconstructed_file_path, intent_info, schema)
        execution_result = code_executor.execute_code(code, reconstructed_file_path)
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
            "original_file": intent_info.get("file_name", os.path.basename(original_file_path)),
            "graph_files": execution_result.get("graph_files", [])
        }
    except Exception as e:
        logger.error(f"Error in analysis: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Analysis failed: {str(e)}"})


@app.get("/api/analyze/stream")
async def stream_analysis(question: str = Query(..., description="User's question")):
    """Stream code generation and analysis via SSE."""
    async def generate():
        try:
            yield {"type": "status", "data": {"message": "Parsing question and selecting file..."}}
            
            intent_info, original_file_path, reconstructed_file_path, schema = _prepare_analysis(question)
            
            yield {
                "type": "file_selected",
                "data": {
                    "file_name": intent_info.get("file_name"),
                    "intent": intent_info.get("intent"),
                    "columns": intent_info.get("required_columns", [])
                }
            }
            
            yield {"type": "status", "data": {"message": "Generating analysis code..."}}
            
            accumulated_code = ""
            async for chunk in code_generator.generate_code_stream(question, reconstructed_file_path, intent_info, schema):
                accumulated_code += chunk
                yield {"type": "code_chunk", "data": {"chunk": chunk}}
            
            yield {"type": "status", "data": {"message": "Executing code..."}}
            
            execution_result = code_executor.execute_code(accumulated_code, reconstructed_file_path)
            
            yield {
                "type": "execution_result",
                "data": {
                    "output": execution_result["output"],
                    "error": execution_result.get("error"),
                    "success": execution_result["success"],
                    "graph_files": execution_result.get("graph_files", [])
                }
            }
            
            used_columns = column_tracker.extract_columns_from_code(accumulated_code, reconstructed_file_path)
            
            yield {
                "type": "column_traceability",
                "data": {
                    "columns_used": used_columns,
                    "original_file": intent_info.get("file_name", os.path.basename(original_file_path))
                }
            }
            
        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            yield {"type": "error", "data": {"error": str(e)}}
    
    async def event_generator():
        try:
            async for event in generate():
                event_data = event["data"].copy()
                event_data["type"] = event["type"]
                yield {
                    "event": event["type"],
                    "data": json.dumps(event_data, ensure_ascii=False)
                }
        finally:
            logger.info("SSE stream completed")
    
    return EventSourceResponse(event_generator())


@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    """WebSocket endpoint for receiving voice transcriptions."""
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            data = await websocket.receive_text()
            transcription_data = json.loads(data)
            question = transcription_data.get("text", "").strip()
            
            if not question or len(question) < 3:
                await websocket.send_json({
                    "type": "error",
                    "error": "No valid question received. Please speak clearly or try again."
                })
                continue
            
            logger.info(f"Received voice transcription: {question}")
            await websocket.send_json({"status": "received", "question": question})
            
            try:
                intent_info, original_file_path, reconstructed_file_path, schema = _prepare_analysis(question)
                
                await websocket.send_json({
                    "status": "file_selected",
                    "file_name": intent_info.get("file_name"),
                    "intent": intent_info.get("intent")
                })
                
                code = code_generator.generate_code(question, reconstructed_file_path, intent_info, schema)
                
                chunk_size = 50
                for i in range(0, len(code), chunk_size):
                    await websocket.send_json({
                        "type": "code_chunk",
                        "chunk": code[i:i + chunk_size]
                    })
                
                execution_result = code_executor.execute_code(code, reconstructed_file_path)
                
                await websocket.send_json({
                    "type": "execution_result",
                    "output": execution_result["output"],
                    "error": execution_result.get("error"),
                    "success": execution_result["success"],
                    "graph_files": execution_result.get("graph_files", [])
                })
                
                used_columns = column_tracker.extract_columns_from_code(code, reconstructed_file_path)
                
                await websocket.send_json({
                    "type": "column_traceability",
                    "columns_used": used_columns,
                    "original_file": intent_info.get("file_name", os.path.basename(original_file_path))
                })
                
            except Exception as e:
                logger.error(f"Error processing voice input: {e}", exc_info=True)
                await websocket.send_json({"type": "error", "error": str(e)})
                
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

