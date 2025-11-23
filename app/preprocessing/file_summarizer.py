"""File summarizer module for generating concise summaries of Excel files and knowledge base functionality."""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

logger = logging.getLogger(__name__)


def _convert_to_serializable(obj: Any) -> Any:
    """
    Convert pandas Timestamp and other non-serializable objects to strings.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable object
    """
    # Check for pandas NA values first (pd.NA is a singleton, not a type)
    if pd.isna(obj):
        return None
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (pd.Int64Dtype, pd.Float64Dtype, pd.BooleanDtype)):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_serializable(item) for item in obj]
    else:
        return obj


class FileSummarizer:
    """Generate and cache concise summaries of Excel files with knowledge base search capabilities."""

    def __init__(self, openai_client, cache_file: str = "file_summaries.json"):
        """
        Initialize the file summarizer.
        
        Args:
            openai_client: OpenAI client instance
            cache_file: Path to JSON file for caching summaries
        """
        self.openai_client = openai_client
        self.cache_file = Path(cache_file)
        self._cache = self._load_cache()
        self._keyword_index = {}
        self._build_index()

    def _load_cache(self) -> Dict:
        """Load summaries from cache file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading cache: {e}")
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save summaries to cache file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def get_summary(self, file_path: str, force_refresh: bool = False) -> Dict:
        """
        Get summary for a file, generating if not cached.
        
        Args:
            file_path: Path to Excel file
            force_refresh: Force regeneration even if cached
            
        Returns:
            Dictionary with summary information
        """
        file_path_str = str(file_path)
        
        # Check cache first
        if not force_refresh and file_path_str in self._cache:
            cached = self._cache[file_path_str]
            # Check if file was modified (simple check - file size and mtime)
            try:
                file_stat = Path(file_path).stat()
                if (cached.get("file_size") == file_stat.st_size and 
                    cached.get("mtime") == file_stat.st_mtime):
                    logger.info(f"Using cached summary for {Path(file_path).name}")
                    return cached
            except Exception:
                pass  # File might not exist, regenerate
        
        # Generate new summary
        logger.info(f"Generating summary for {Path(file_path).name}")
        summary = self._generate_summary(file_path)
        
        # Cache it
        try:
            file_stat = Path(file_path).stat()
            summary["file_size"] = file_stat.st_size
            summary["mtime"] = file_stat.st_mtime
        except Exception:
            pass
        
        self._cache[file_path_str] = summary
        self._save_cache()
        self._build_index()  # Rebuild index after adding new summary
        
        return summary

    def _generate_summary(self, file_path: str) -> Dict:
        """
        Generate summary using OpenAI (cheap model).
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            Dictionary with summary information
        """
        try:
            # Read sample data from file
            file_info = self._extract_file_info(file_path)
            
            system_prompt = '''You are a data analysis expert. Your task is to generate a concise summary of an Excel file's content and purpose.

Generate a summary that includes:
1. What type of data the file contains (e.g., sales data, financial records, inventory)
2. The main purpose/use case of the file
3. Key data categories or dimensions (e.g., time periods, regions, product types)
4. Important metrics or measures if apparent

Keep the summary concise (2-3 sentences) and focused on helping identify when this file is relevant to a user's question.'''
            
            user_prompt = f'''Analyze this Excel file and generate a concise summary:

File name: {file_info["file_name"]}
Number of sheets: {len(file_info["sheets"])}
Sheet names: {", ".join(file_info["sheets"])}

Column information:
{file_info["columns_info"]}

Sample data (first 3 rows):
{file_info["sample_data"]}

Generate a concise summary of the file's content and purpose.'''
            
            response = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=200  # Keep it concise
            )
            
            summary_text = response.choices[0].message.content.strip()
            
            return {
                "file_path": file_path,
                "file_name": file_info["file_name"],
                "summary": summary_text,
                "sheets": file_info["sheets"],
                "column_count": file_info["column_count"],
                "row_count": file_info["row_count"]
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            # Fallback summary
            return {
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "summary": f"Excel file: {Path(file_path).name}",
                "sheets": [],
                "column_count": 0,
                "row_count": 0
            }

    def _extract_file_info(self, file_path: str) -> Dict:
        """
        Extract basic information from Excel file.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            Dictionary with file information
        """
        try:
            # Read first sheet
            df = pd.read_excel(file_path, sheet_name=0, nrows=5)
            
            # Get all sheet names
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            # Get column info
            columns = list(df.columns)
            column_info = []
            for col in columns[:20]:  # Limit to first 20 columns
                col_type = str(df[col].dtype)
                sample_values = df[col].dropna().head(3).tolist()
                column_info.append({
                    "name": str(col),
                    "type": col_type,
                    "sample_values": [str(v) for v in sample_values]
                })
            
            # Get row count (approximate)
            try:
                full_df = pd.read_excel(file_path, sheet_name=0)
                row_count = len(full_df)
            except:
                row_count = len(df)
            
            # Format sample data
            sample_data = df.head(3).to_dict('records')
            # Convert pandas Timestamp and other non-serializable types to strings
            sample_data = _convert_to_serializable(sample_data)
            sample_data_str = json.dumps(sample_data, ensure_ascii=False, indent=2)
            
            return {
                "file_name": Path(file_path).name,
                "sheets": sheet_names,
                "columns_info": json.dumps(column_info, ensure_ascii=False, indent=2),
                "sample_data": sample_data_str,
                "column_count": len(columns),
                "row_count": row_count
            }
            
        except Exception as e:
            logger.error(f"Error extracting file info: {e}", exc_info=True)
            return {
                "file_name": Path(file_path).name,
                "sheets": [],
                "columns_info": "[]",
                "sample_data": "[]",
                "column_count": 0,
                "row_count": 0
            }

    def summarize_all_files(self, file_paths: list) -> Dict[str, Dict]:
        """
        Generate summaries for multiple files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary mapping file paths to summaries
        """
        summaries = {}
        for file_path in file_paths:
            try:
                summaries[file_path] = self.get_summary(file_path)
            except Exception as e:
                logger.error(f"Error summarizing {file_path}: {e}")
        
        self._build_index()  # Rebuild index after summarizing all files
        return summaries

    def _build_index(self) -> None:
        """Build search index from cached summaries."""
        self._keyword_index = {}
        for file_path, summary_data in self._cache.items():
            summary_text = summary_data.get("summary", "").lower()
            keywords = self._extract_keywords(summary_text)
            for keyword in keywords:
                if keyword not in self._keyword_index:
                    self._keyword_index[keyword] = []
                self._keyword_index[keyword].append(file_path)

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text (simple approach).
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords
        """
        # Remove punctuation and split
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                     'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were',
                     'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
                     'did', 'will', 'would', 'could', 'should', 'may', 'might',
                     'this', 'that', 'these', 'those', 'file', 'data', 'contains'}
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        return keywords

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for relevant files based on query.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of file summaries sorted by relevance
        """
        query_lower = query.lower()
        query_keywords = self._extract_keywords(query_lower)
        
        # Score files based on keyword matches
        file_scores = {}
        for keyword in query_keywords:
            if keyword in self._keyword_index:
                for file_path in self._keyword_index[keyword]:
                    file_scores[file_path] = file_scores.get(file_path, 0) + 1
        
        # Also check for exact phrase matches in summaries
        for file_path, summary_data in self._cache.items():
            summary_text = summary_data.get("summary", "").lower()
            if query_lower in summary_text:
                file_scores[file_path] = file_scores.get(file_path, 0) + 3  # Higher weight
        
        # Sort by score
        sorted_files = sorted(
            file_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # Return full summary data
        results = []
        for file_path, score in sorted_files:
            summary_data = self._cache.get(file_path, {})
            results.append({
                **summary_data,
                "relevance_score": score
            })
        
        return results

    def get_all_summaries(self) -> Dict:
        """Get all cached summaries."""
        return self._cache

