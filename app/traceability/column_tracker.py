"""Data traceability module to track and report which columns were used."""

import ast
import logging
import re
from typing import List, Set

import pandas as pd

logger = logging.getLogger(__name__)


class ColumnTracker:
    """Track which Excel columns are used in generated code."""

    def extract_columns_from_code(self, code: str, file_path: str) -> List[str]:
        """
        Parse code to find column references.
        
        Args:
            code: Python code string
            file_path: Path to Excel file
            
        Returns:
            List of column names that were used
        """
        try:
            # Get actual columns from the file
            actual_columns = self._get_file_columns(file_path)
            
            # Extract column references from code
            used_columns = set()
            
            # Method 1: Parse AST to find column access patterns
            used_columns.update(self._extract_from_ast(code, actual_columns))
            
            # Method 2: Use regex patterns for common pandas operations
            used_columns.update(self._extract_from_regex(code, actual_columns))
            
            # Validate columns exist in file
            valid_columns = [col for col in used_columns if col in actual_columns]
            
            logger.info(f"Extracted columns from code: {valid_columns}")
            return sorted(valid_columns)
            
        except Exception as e:
            logger.error(f"Error extracting columns: {e}", exc_info=True)
            return []

    def _get_file_columns(self, file_path: str) -> List[str]:
        """
        Get column names from Excel file.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            List of column names
        """
        try:
            df = pd.read_excel(file_path, sheet_name=0, nrows=1)
            return list(df.columns)
        except Exception as e:
            logger.error(f"Error reading columns from {file_path}: {e}")
            return []

    def _extract_from_ast(self, code: str, valid_columns: List[str]) -> Set[str]:
        """
        Extract column references by parsing the AST.
        
        Args:
            code: Python code string
            valid_columns: List of valid column names
            
        Returns:
            Set of column names found
        """
        columns = set()
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Pattern: df['column_name'] or df["column_name"] or df[['col1', 'col2']]
                if isinstance(node, ast.Subscript) and isinstance(node.value, (ast.Name, ast.Attribute)):
                    if isinstance(node.slice, ast.Constant):
                        col_name = node.slice.value
                        if isinstance(col_name, str) and col_name in valid_columns:
                            columns.add(col_name)
                    elif isinstance(node.slice, ast.Str):  # Python < 3.8
                        if node.slice.s in valid_columns:
                            columns.add(node.slice.s)
                    elif isinstance(node.slice, (ast.List, ast.Tuple)):
                        # Pattern: df[['col1', 'col2']]
                        for elt in node.slice.elts:
                            col_name = (elt.value if isinstance(elt, ast.Constant) 
                                      else elt.s if isinstance(elt, ast.Str) else None)
                            if isinstance(col_name, str) and col_name in valid_columns:
                                columns.add(col_name)
                
                # Pattern: df.column_name
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, (ast.Name, ast.Attribute)) and node.attr in valid_columns:
                        columns.add(node.attr)
                                    
        except SyntaxError as e:
            logger.warning(f"Could not parse code AST: {e}")
        except Exception as e:
            logger.warning(f"Error extracting from AST: {e}")
        
        return columns

    def _extract_from_regex(self, code: str, valid_columns: List[str]) -> Set[str]:
        """
        Extract column references using regex patterns.
        
        Args:
            code: Python code string
            valid_columns: List of valid column names
            
        Returns:
            Set of column names found
        """
        columns = set()
        
        # Pattern 1: df['column'] or df["column"]
        pattern1 = r"df\[['\"]([^'\"]+)['\"]\]"
        matches = re.findall(pattern1, code)
        for match in matches:
            if match in valid_columns:
                columns.add(match)
        
        # Pattern 2: df[['col1', 'col2']] - multiple columns
        pattern2 = r"df\[\[([^\]]+)\]\]"
        matches = re.findall(pattern2, code)
        for match in matches:
            # Extract individual column names
            col_matches = re.findall(r"['\"]([^'\"]+)['\"]", match)
            for col in col_matches:
                if col in valid_columns:
                    columns.add(col)
        
        # Pattern 3: df.column_name (simple attribute access)
        # This is less reliable, so we check against valid columns
        for col in valid_columns:
            # Look for patterns like df.col_name or filtered_df.col_name
            pattern = rf"\b\w+\.{re.escape(col)}\b"
            if re.search(pattern, code):
                columns.add(col)
        
        # Pattern 4: .groupby(['column']) or similar operations
        pattern4 = r"\.groupby\(\[?['\"]([^'\"]+)['\"]\]?"
        matches = re.findall(pattern4, code)
        for match in matches:
            if match in valid_columns:
                columns.add(match)
        
        # Pattern 5: .sort_values(by=['column'])
        pattern5 = r"sort_values\([^)]*by\s*=\s*\[?['\"]([^'\"]+)['\"]"
        matches = re.findall(pattern5, code)
        for match in matches:
            if match in valid_columns:
                columns.add(match)
        
        return columns


