"""Code generation module for creating Python analysis code."""

import logging
import os
from typing import AsyncIterator, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generate Python code for Excel data analysis using OpenAI."""

    def __init__(self, openai_client):
        """Initialize the code generator."""
        self.openai_client = openai_client

    async def generate_code_stream(self, question: str, file_path: str, 
                                   intent_info: Dict, schema: Optional[Dict] = None) -> AsyncIterator[str]:
        """Stream code generation via OpenAI."""
        try:
            prompt = self._build_prompt(question, file_path, intent_info, schema)
            
            stream = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                    
        except Exception as e:
            logger.error(f"Error generating code: {e}", exc_info=True)
            yield f"# Error generating code: {str(e)}\n"

    def generate_code(self, question: str, file_path: str, intent_info: Dict, schema: Optional[Dict] = None) -> str:
        """Generate code synchronously (non-streaming)."""
        try:
            prompt = self._build_prompt(question, file_path, intent_info, schema)
            
            response = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            code = response.choices[0].message.content.strip()
            return self._format_code_response(code)
            
        except Exception as e:
            logger.error(f"Error generating code: {e}", exc_info=True)
            return f"# Error generating code: {str(e)}\n"

    def _get_system_prompt(self) -> str:
        """Get the system prompt with code generation rules."""
        return '''You are an expert Python data analyst specializing in pandas. Generate clean, executable Python code for Excel data analysis.

**CRITICAL: File Path Usage**
- The variable `file_path` is ALREADY DEFINED in the execution context
- ALWAYS use `file_path` variable to read Excel files: `df = pd.read_excel(file_path, ...)`
- NEVER hardcode file paths in your generated code
- The file path shown in the prompt is for reference only - use the variable

**Excel Data Processing Rules**

1. Basic Code Structure Requirements:
   1.1 Necessary imports and settings:
   ```python
   import pandas as pd
   import warnings
   warnings.simplefilter(action='ignore', category=Warning)
   pd.set_option('display.max_columns', None)
   pd.set_option('display.max_rows', None)
   pd.set_option('display.width', None)
   pd.set_option('display.max_colwidth', None)
   ```
   1.2 Output format requirements:
   - Output only code, no additional explanations
   - Do not include Markdown code block markers (```python or ```)
   - Output pure Python code as plain text
   - All results must be printed to console using "print"

2. Data Query and Processing Requirements:
   2.1 Multi-row data processing:
   - Before generating code, determine if user wants data in a "range" or "specific value" based on Excel structure
   - When sorting results, explicitly specify `ascending=False` (descending) or `True` (ascending), avoid default sorting
   2.2 Key field processing:
   - Time fields must be converted using `pd.to_datetime(..., errors='coerce').dt.normalize()` and extract year/month/day components for comparison
   - For identifier fields, use `.astype(str)` for string conversion to avoid format issues (leading zeros, scientific notation, precision truncation)
   - Numeric fields must be converted using `pd.to_numeric(..., errors='coerce')` to avoid string comparison
   - For numerical calculations (sum, comparison, aggregation, sorting), use "pd.to_numeric(data, errors='coerce')" to convert to numeric type before calculation, ignoring unconvertible values
   2.3 String matching and filtering (CRITICAL for Chinese and mixed-language data):
   - When filtering by identifier values (e.g., "18号", "motor 18", "第18号"), use flexible matching:
     * First convert the identifier column to string: `df['column'].astype(str)`
     * Strip whitespace: `.str.strip()`
     * Use flexible matching patterns:
       - For exact match: `df[df['column'].astype(str).str.strip() == 'value']`
       - For partial match: `df[df['column'].astype(str).str.strip().str.contains('value', na=False, regex=False)]`
     * When the question mentions a number (e.g., "18号", "第18号"), extract just the numeric part and match flexibly:
       - Try matching the full string first: `df[df['column'].astype(str).str.strip().str.contains('18号', na=False, regex=False)]`
       - If that fails, try matching just the number: `df[df['column'].astype(str).str.strip().str.contains('18', na=False, regex=False)]`
       - Or use regex: `df[df['column'].astype(str).str.strip().str.contains(r'18|第18|18号', na=False, regex=True)]`
   - Always check column existence before filtering: `if 'column_name' in df.columns:`
   - Handle column names with spaces or special characters exactly as they appear in the schema
   - When column names have multiple spaces, preserve them exactly (e.g., "电机  编号" has two spaces)
   2.4 Data cleaning and processing:
   - The "DataFrame.fillna" method with "method" parameter is deprecated
   - Keep special characters in column names (underscores, multiple spaces) unchanged
   - Normalize whitespace in data values but preserve column name structure
   2.5 Output specifications:
   - Format and print line by line for batch output

3. Code Robustness Requirements:
   3.1 Exception handling:
   - Code must include exception handling, wrap file operations and data processing logic in try-except
   - Catch common exceptions like FileNotFoundError, KeyError and provide friendly messages
   - When printing exceptions, include specific error information: print(f"Error details: {str(e)}")
   3.2 Data validation:
   - Check df.empty immediately after reading data to avoid operating on empty DataFrame
   - For key filter fields (like "customer_name" or Chinese column names), first confirm existence with `if 'column_name' in df.columns:`
   - If a filter returns empty results, print a helpful message showing what was searched and what columns/values are available
   - If file has multiple sheets, generate code for each qualifying sheet
   3.3 Column name matching:
   - Use exact column names as provided in the schema (preserve spaces, special characters)
   - When filtering, always verify the column exists before using it
   - If a column name in the question doesn't match exactly, try to find the closest match or list available columns

4. Naming Conventions:
   4.1 Variable and function naming:
   - Avoid using symbols like # in function or variable names (it's a comment symbol in many languages)
   - Avoid using Chinese characters in function or variable names (may cause syntax errors)
   - Use meaningful English variable names like filtered_df, result_data, etc.

5. Problem Decomposition Principles:
   5.1 Analyze user needs:
   - First parse key dimensions of user's question
   - Convert natural language descriptions to corresponding pandas operation chains
   5.2 Defensive programming:
   - Assume raw data may have missing values, type confusion, or special characters

6. Chart Generation:
   - If user's question indicates need for a chart, use "import plotly.graph_objects as go" to generate an interactive local HTML page
   - Use go.Figure with mode parameter value "lines+markers+text"
   - fig.update_layout must include title (centered), xaxis_title, yaxis_title
   - Sort X-axis data from small to large before plotting
   - ALWAYS print the filename after saving: print(f"Chart saved to: {filename}") or print("Chart saved to: filename.html")
   - Example: fig.write_html('chart.html'); print("Chart saved to: chart.html")
'''

    def _build_prompt(self, question: str, file_path: str, intent_info: Dict, schema: Optional[Dict] = None) -> str:
        """Build the prompt for code generation."""
        try:
            if schema:
                columns = schema.get('headers', [])
                required_columns = intent_info.get('required_columns', columns)
                
                schema_lines = []
                schema_lines.append(f"File: {schema.get('file_name', 'unknown')}")
                schema_lines.append(f"Sheet: {schema.get('sheet_name', 'unknown')}")
                schema_lines.append(f"Total rows: {schema.get('total_rows', 0)}, Total columns: {schema.get('total_columns', 0)}")
                schema_lines.append("")
                schema_lines.append("Columns with data types:")
                for header in columns:
                    col_type = schema.get('column_types', {}).get(header, {})
                    readable_type = col_type.get('readable_type', 'unknown')
                    schema_lines.append(f"  - {header} ({readable_type})")
                
                if schema.get('first_5_rows'):
                    schema_lines.append("")
                    schema_lines.append("First 5 rows (sample data):")
                    for i, row in enumerate(schema['first_5_rows'], 1):
                        row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                        schema_lines.append(f"  Row {i}: {row_str}")
                
                if schema.get('last_5_rows'):
                    schema_lines.append("")
                    schema_lines.append("Last 5 rows (sample data):")
                    for i, row in enumerate(schema['last_5_rows'], 1):
                        row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                        schema_lines.append(f"  Row {i}: {row_str}")
                
                schema_text = "\n".join(schema_lines)
                
                prompt = f'''User question: {question}

Target Excel file: {file_path}
File name: {os.path.basename(file_path)}

Analysis intent: {intent_info.get('intent', 'general_analysis')}
Required columns: {required_columns}

Table Schema (from reconstructed table):
{schema_text}

Please generate Python code to:
1. Read the Excel file using the variable `file_path` (already defined in the execution context)
2. Perform the analysis requested in the question
3. Print the results

Important:
- ALWAYS use the variable `file_path` to read the Excel file: `df = pd.read_excel(file_path, ...)`
- Do NOT hardcode the file path - use the `file_path` variable that is already available
- The file path shown above ({file_path}) is for reference only - use the variable in your code
- The table has been reconstructed and cleaned - use the column names EXACTLY as shown in the schema (preserve spaces, special characters)
- Handle the columns: {required_columns}
- Pay attention to data types: {', '.join([f"{col}: {schema.get('column_types', {}).get(col, {}).get('readable_type', 'unknown')}" for col in columns[:10]])}
- For filtering by identifier values (especially Chinese text with numbers like "18号", "第18号"):
  * Convert identifier columns to string: `.astype(str)`
  * Strip whitespace: `.str.strip()`
  * Use flexible matching (try full match first, then partial match)
  * If no results found, print available values from that column for debugging
- Always verify column existence before filtering: `if 'column_name' in df.columns:`
- Include proper error handling with helpful messages
- Print all results clearly
- If charts are needed, generate interactive HTML files using plotly and save them to the current working directory (output folder)
- IMPORTANT: After saving a chart with fig.write_html(), always print the filename: print(f"Chart saved to: filename.html")'''
            else:
                df = pd.read_excel(file_path, sheet_name=0, nrows=5)
                columns = list(df.columns)
                sample_data = df.head(3).to_dict('records')
                
                prompt = f'''User question: {question}

Target Excel file: {file_path}
File name: {os.path.basename(file_path)}

Analysis intent: {intent_info.get('intent', 'general_analysis')}
Required columns: {intent_info.get('required_columns', columns)}

Available columns in the file:
{columns}

Sample data (first 3 rows):
{self._format_sample_data(sample_data)}

Please generate Python code to:
1. Read the Excel file using the variable `file_path` (already defined in the execution context)
2. Perform the analysis requested in the question
3. Print the results

Important:
- ALWAYS use the variable `file_path` to read the Excel file: `df = pd.read_excel(file_path, ...)`
- Do NOT hardcode the file path - use the `file_path` variable that is already available
- The file path shown above ({file_path}) is for reference only - use the variable in your code
- Handle the columns: {intent_info.get('required_columns', columns)}
- For filtering by identifier values (especially Chinese text with numbers like "18号", "第18号"):
  * Convert identifier columns to string: `.astype(str)`
  * Strip whitespace: `.str.strip()`
  * Use flexible matching (try full match first, then partial match)
  * If no results found, print available values from that column for debugging
- Always verify column existence before filtering: `if 'column_name' in df.columns:`
- Include proper error handling with helpful messages
- Print all results clearly
- If charts are needed, generate interactive HTML files using plotly and save them to the current working directory (output folder)
- IMPORTANT: After saving a chart with fig.write_html(), always print the filename: print(f"Chart saved to: filename.html")'''
            
            return prompt
            
        except Exception as e:
            logger.error(f"Error building prompt: {e}", exc_info=True)
            return f"User question: {question}\n\nTarget file: {file_path}\n\nGenerate Python code to analyze this Excel file."

    def _format_sample_data(self, sample_data: list) -> str:
        """Format sample data for the prompt."""
        if not sample_data:
            return "No sample data available"
        return "\n".join(f"Row {i}: {', '.join(f'{k}: {v}' for k, v in row.items())}" 
                        for i, row in enumerate(sample_data, 1))

    def _format_code_response(self, code: str) -> str:
        """Clean and format the generated code."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        
        return code.strip()

