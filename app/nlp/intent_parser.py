"""Natural language processing module for parsing user questions and selecting files."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from app.preprocessing.file_summarizer import FileSummarizer

logger = logging.getLogger(__name__)


class IntentParser:
    """Parse user questions to extract intent, select files, and identify columns."""

    def __init__(self, openai_client, sheets_dir: str = "sheets"):
        """
        Initialize the intent parser.
        
        Args:
            openai_client: OpenAI client instance
            sheets_dir: Directory containing Excel files
        """
        self.openai_client = openai_client
        self.sheets_dir = Path(sheets_dir)
        self._file_metadata_cache = {}
        
        # Initialize file summarizer (includes knowledge base functionality)
        self.file_summarizer = FileSummarizer(openai_client, cache_file="file_summaries.json")
        
        # Build/update knowledge base on initialization
        self._build_knowledge_base()

    def parse_intent(self, question: str) -> Dict:
        """
        Parse user question to extract intent and select target file(s).
        
        Args:
            question: User's natural language question
            
        Returns:
            Dictionary with intent, file_path, columns, and other metadata
        """
        try:
            # Get available files
            available_files = self._list_available_files()
            if not available_files:
                raise ValueError("No Excel files found in sheets directory")
            
            # Step 1: Use knowledge base to filter relevant files (cheap filtering)
            relevant_files = self._filter_relevant_files(question, available_files, top_k=5)
            logger.info(f"Knowledge base filtered {len(available_files)} files to {len(relevant_files)} relevant files")
            
            # Step 2: Get metadata only for relevant files (saves API tokens)
            files_metadata = {}
            for file_path in relevant_files:
                try:
                    metadata = self._get_file_metadata(file_path)
                    files_metadata[file_path] = metadata
                except Exception as e:
                    logger.warning(f"Could not get metadata for {file_path}: {e}")
            
            # Step 3: Use OpenAI to parse intent and select file (from filtered set)
            result = self._parse_with_openai(question, files_metadata)
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing intent: {e}", exc_info=True)
            raise

    def _list_available_files(self) -> List[str]:
        """List all Excel files in the sheets directory."""
        if not self.sheets_dir.exists():
            logger.warning(f"Sheets directory does not exist: {self.sheets_dir}")
            return []
        
        excel_files = list(self.sheets_dir.glob("*.xlsx")) + list(self.sheets_dir.glob("*.xls"))
        return [str(f) for f in excel_files]

    def _build_knowledge_base(self) -> None:
        """Build or update knowledge base with file summaries."""
        try:
            available_files = self._list_available_files()
            if not available_files:
                return
            
            logger.info("Building knowledge base from file summaries...")
            
            # Generate summaries for all files (automatically cached and indexed)
            summaries = self.file_summarizer.summarize_all_files(available_files)
            
            logger.info(f"Knowledge base updated with {len(summaries)} file summaries")
            
        except Exception as e:
            logger.warning(f"Error building knowledge base: {e}")

    def _filter_relevant_files(self, question: str, available_files: List[str], top_k: int = 5) -> List[str]:
        """
        Use knowledge base to filter relevant files.
        
        Args:
            question: User's question
            available_files: List of all available files
            top_k: Number of top files to return
            
        Returns:
            List of relevant file paths
        """
        try:
            # Search using file summarizer's knowledge base functionality
            results = self.file_summarizer.search(question, top_k=top_k)
            
            # Extract file paths
            relevant_paths = [r["file_path"] for r in results]
            
            # If knowledge base doesn't have enough results, include all files
            if len(relevant_paths) < top_k:
                # Add remaining files that weren't in top results
                for file_path in available_files:
                    if file_path not in relevant_paths:
                        relevant_paths.append(file_path)
                        if len(relevant_paths) >= top_k:
                            break
            
            return relevant_paths[:top_k] if relevant_paths else available_files[:top_k]
            
        except Exception as e:
            logger.warning(f"Error filtering files with knowledge base: {e}, using all files")
            return available_files[:top_k]

    def _get_file_metadata(self, file_path: str) -> Dict:
        """
        Get metadata about an Excel file (column names, sample data).
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            Dictionary with file metadata
        """
        # Check cache
        if file_path in self._file_metadata_cache:
            return self._file_metadata_cache[file_path]
        
        try:
            # Read first sheet to get column info
            df = pd.read_excel(file_path, sheet_name=0, nrows=10)
            
            # Convert sample data to JSON-serializable format
            sample_data = df.head(3).to_dict('records')
            # Convert Timestamp and other non-JSON types to strings
            for record in sample_data:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, (pd.Timestamp, pd.Timedelta)):
                        record[key] = str(value)
                    elif hasattr(value, 'isoformat'):  # datetime objects
                        record[key] = value.isoformat()
                    else:
                        # Try to convert to native Python type
                        try:
                            json.dumps(value)  # Test if serializable
                        except (TypeError, ValueError):
                            record[key] = str(value)
            
            metadata = {
                "file_name": Path(file_path).name,
                "columns": list(df.columns),
                "sample_data": sample_data,
                "row_count": len(pd.read_excel(file_path, sheet_name=0)),
                "sheets": pd.ExcelFile(file_path).sheet_names
            }
            
            # Cache the result
            self._file_metadata_cache[file_path] = metadata
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata for {file_path}: {e}", exc_info=True)
            raise

    def _parse_with_openai(self, question: str, files_metadata: Dict) -> Dict:
        """
        Use OpenAI to parse the question and select appropriate file.
        
        Args:
            question: User's question
            files_metadata: Dictionary mapping file paths to their metadata
            
        Returns:
            Dictionary with parsed intent information
        """
        try:
            # Build context about available files
            files_context = []
            for file_path, metadata in files_metadata.items():
                files_context.append({
                    "file_path": file_path,
                    "file_name": metadata["file_name"],
                    "columns": metadata["columns"],
                    "sample_data": metadata["sample_data"][:2]  # First 2 rows
                })
            
            system_prompt = '''You are an expert data analysis assistant. Your task is to:
1. Understand the user's question and identify the analysis intent (summation, grouping, trend analysis, sorting, filtering, etc.)
2. Select the most appropriate Excel file from the available files
3. Identify which columns from the selected file are needed for the analysis

Return a JSON object with the following structure:
{
    "intent": "intent_type",  // e.g., "summation", "grouping", "trend_analysis", "sorting", "filtering", "statistical_summary"
    "target_file": "file_path",  // Full path to the selected Excel file
    "required_columns": ["column1", "column2", ...],  // List of column names needed
    "reasoning": "brief explanation"  // Why this file and columns were selected
}'''
            
            user_prompt = f'''User question: {question}

Available Excel files:
{json.dumps(files_context, ensure_ascii=False, indent=2)}

Please analyze the question and return the JSON response as specified.'''
            
            response = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate the result
            if "target_file" not in result or not os.path.exists(result["target_file"]):
                raise ValueError(f"Selected file does not exist: {result.get('target_file')}")
            
            # Get actual columns from the file
            actual_columns = self._get_file_metadata(result["target_file"])["columns"]
            
            # Filter required columns to only those that exist
            required_columns = [
                col for col in result.get("required_columns", [])
                if col in actual_columns
            ]
            
            result["required_columns"] = required_columns
            result["all_columns"] = actual_columns
            
            logger.info(f"Parsed intent: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing with OpenAI: {e}", exc_info=True)
            raise


