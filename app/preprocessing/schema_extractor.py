"""Schema extraction module for extracting structural information from reconstructed Excel tables."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class SchemaExtractor:
    """Extract schema information from reconstructed Excel tables."""


    def extract_schema(self, file_path: str, sheet_name: Optional[str] = None) -> Dict:
        """
        Extract schema from a reconstructed Excel file.
        
        Args:
            file_path: Path to reconstructed Excel file
            sheet_name: Optional sheet name (uses first sheet if None)
            
        Returns:
            Dictionary with schema information
        """
        try:
            # Read the reconstructed file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path, sheet_name=0)
            
            if df.empty:
                logger.warning(f"Empty DataFrame in {file_path}")
                return self._empty_schema(file_path)
            
            # Extract table header (column names)
            headers = list(df.columns)
            
            # Extract data types for each column
            column_types = {}
            for col in headers:
                dtype = str(df[col].dtype)
                # Map pandas dtypes to more readable types
                readable_type = self._map_dtype(dtype)
                column_types[col] = {
                    "pandas_dtype": dtype,
                    "readable_type": readable_type
                }
            
            # Extract first 5 rows
            first_rows = df.head(5)
            first_rows_data = first_rows.to_dict('records')
            
            # Extract last 5 rows
            last_rows = df.tail(5)
            last_rows_data = last_rows.to_dict('records')
            
            # Get total row count
            total_rows = len(df)
            
            # Get sheet names if multiple sheets exist
            excel_file = pd.ExcelFile(file_path)
            all_sheets = excel_file.sheet_names
            
            schema = {
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "sheet_name": sheet_name or excel_file.sheet_names[0],
                "all_sheets": all_sheets,
                "total_rows": total_rows,
                "total_columns": len(headers),
                "headers": headers,
                "column_types": column_types,
                "first_5_rows": first_rows_data,
                "last_5_rows": last_rows_data
            }
            
            logger.info(f"Extracted schema from {Path(file_path).name}: {len(headers)} columns, {total_rows} rows")
            return schema
            
        except Exception as e:
            logger.error(f"Error extracting schema from {file_path}: {e}", exc_info=True)
            return self._empty_schema(file_path)

    def _map_dtype(self, dtype: str) -> str:
        """
        Map pandas dtype to readable type.
        
        Args:
            dtype: Pandas dtype string
            
        Returns:
            Readable type string
        """
        dtype_lower = dtype.lower()
        
        if 'int' in dtype_lower:
            return 'integer'
        elif 'float' in dtype_lower:
            return 'float'
        elif 'bool' in dtype_lower:
            return 'boolean'
        elif 'datetime' in dtype_lower or 'date' in dtype_lower:
            return 'datetime'
        elif 'object' in dtype_lower or 'string' in dtype_lower:
            return 'string'
        else:
            return dtype

    def _empty_schema(self, file_path: str) -> Dict:
        """Return empty schema structure."""
        return {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "sheet_name": None,
            "all_sheets": [],
            "total_rows": 0,
            "total_columns": 0,
            "headers": [],
            "column_types": {},
            "first_5_rows": [],
            "last_5_rows": []
        }

    def format_schema_for_llm(self, schema: Dict) -> str:
        """
        Format schema information for LLM context.
        
        Args:
            schema: Schema dictionary
            
        Returns:
            Formatted string for LLM prompt
        """
        lines = []
        
        lines.append(f"File: {schema['file_name']}")
        lines.append(f"Sheet: {schema['sheet_name']}")
        if len(schema['all_sheets']) > 1:
            lines.append(f"All sheets: {', '.join(schema['all_sheets'])}")
        lines.append(f"Total rows: {schema['total_rows']}, Total columns: {schema['total_columns']}")
        lines.append("")
        
        lines.append("Table Structure:")
        lines.append("=" * 50)
        
        # Column information with types
        lines.append("\nColumns:")
        for i, header in enumerate(schema['headers'], 1):
            col_type = schema['column_types'].get(header, {})
            readable_type = col_type.get('readable_type', 'unknown')
            lines.append(f"  {i}. {header} ({readable_type})")
        
        # First 5 rows
        if schema['first_5_rows']:
            lines.append("\nFirst 5 rows (sample data):")
            lines.append("-" * 50)
            for i, row in enumerate(schema['first_5_rows'], 1):
                row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                lines.append(f"  Row {i}: {row_str}")
        
        # Last 5 rows
        if schema['last_5_rows']:
            lines.append("\nLast 5 rows (sample data):")
            lines.append("-" * 50)
            for i, row in enumerate(schema['last_5_rows'], 1):
                row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                lines.append(f"  Row {i}: {row_str}")
        
        return "\n".join(lines)

