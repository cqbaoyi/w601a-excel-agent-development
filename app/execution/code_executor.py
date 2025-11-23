"""Code execution module for safely executing generated Python code."""

import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jupyter_client.manager import start_new_kernel

logger = logging.getLogger(__name__)


class CodeExecutor:
    """Execute Python code safely using Jupyter kernel."""

    def execute_code(self, code: str, file_path: str) -> Dict[str, str]:
        """
        Execute generated Python code with file context.
        
        Args:
            code: Python code to execute
            file_path: Path to the Excel file being analyzed
            
        Returns:
            Dictionary with 'output', 'error', 'success', and 'graph_files' keys
        """
        kernel_manager = None
        client = None
        
        output_dir = Path(__file__).parent.parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        expected_html_files = self._extract_html_files_from_code(code, output_dir)
        logger.info(f"Found {len(expected_html_files)} HTML file(s) in generated code: {expected_html_files}")
        
        try:
            kernel_manager, client = start_new_kernel()
            logger.info("Jupyter kernel started")
            
            full_code = self._prepare_code(code, file_path)
            client.execute(full_code)
            output, error = self._capture_output(client)
            
            time.sleep(0.5)
            
            verified_files = self._verify_html_files_exist(expected_html_files, output_dir, max_retries=5)
            html_files_from_output = self._extract_html_files_from_output(output, output_dir)
            all_detected = set(verified_files) | set(html_files_from_output)
            new_html_files = list(all_detected)
            
            if new_html_files:
                logger.info(f"Verified {len(new_html_files)} HTML file(s): {new_html_files}")
            elif expected_html_files:
                logger.warning(f"Expected {len(expected_html_files)} HTML file(s) but none verified")
            
            return {
                "output": output,
                "error": error,
                "success": error is None,
                "graph_files": new_html_files
            }
            
        except Exception as e:
            logger.error(f"Error executing code: {e}", exc_info=True)
            return {
                "output": "",
                "error": f"Execution failed: {str(e)}",
                "success": False,
                "graph_files": []
            }
            
        finally:
            if client:
                try:
                    client.stop_channels()
                except Exception as e:
                    logger.error(f"Error stopping channels: {e}")
            
            if kernel_manager:
                try:
                    kernel_manager.shutdown_kernel()
                except Exception as e:
                    logger.error(f"Error shutting down kernel: {e}")

    def _prepare_code(self, code: str, file_path: str) -> str:
        """Prepare code for execution by adding necessary context."""
        import os
        from pathlib import Path
        
        abs_file_path = Path(file_path).absolute()
        if not abs_file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {abs_file_path}")
        
        output_dir = Path(__file__).parent.parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        abs_file_path_str = str(abs_file_path).replace('\\', '\\\\')
        
        prepended = f'''import os
from pathlib import Path

# File path variable - use this to read the Excel file
file_path = r"{abs_file_path_str}"  # Absolute path to Excel file

# Verify file exists before proceeding
if not os.path.exists(file_path):
    print(f"ERROR: File not found: {{file_path}}")
    print(f"Current working directory: {{os.getcwd()}}")
    print(f"File path type: {{type(file_path)}}")
    raise FileNotFoundError(f"The specified file was not found: {{file_path}}. Please check the file path.")

# Set up output directory for generated files (charts, etc.)
output_dir = Path(r"{output_dir}")
output_dir.mkdir(exist_ok=True)
os.chdir(str(output_dir))  # Change working directory to output folder

'''
        return prepended + code

    def _capture_output(self, client, timeout: int = 30) -> Tuple[str, Optional[str]]:
        """
        Capture output from code execution.
        
        Args:
            client: Jupyter client instance
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (output, error)
        """
        output_lines = []
        error = None
        
        while True:
            try:
                msg = client.get_iopub_msg(timeout=timeout)
                msg_type = msg['header']['msg_type']
                content = msg['content']
                
                if msg_type == 'stream':
                    text = content.get('text', '')
                    if text:
                        output_lines.append(text)
                elif msg_type == 'execute_result':
                    if 'text/plain' in content.get('data', {}):
                        output_lines.append(content['data']['text/plain'])
                elif msg_type == 'error':
                    traceback = content.get('traceback', [])
                    error = '\n'.join(traceback)
                    logger.error(f"Code execution error: {error}")
                    break
                elif msg_type == 'status':
                    if content.get('execution_state') == 'idle':
                        break
                        
            except Exception as e:
                logger.error(f"Error capturing output: {str(e)}")
                break
        
        output = '\n'.join(output_lines) if output_lines else "No output"
        return output, error
    
    def _get_html_files(self, output_dir: Path) -> List[str]:
        """
        Get list of HTML files in the output directory.
        
        Args:
            output_dir: Path to output directory
            
        Returns:
            List of HTML file names
        """
        try:
            html_files = [f.name for f in output_dir.glob("*.html")]
            return html_files
        except Exception as e:
            logger.error(f"Error getting HTML files: {e}")
            return []
    
    def _extract_html_files_from_code(self, code: str, output_dir: Path) -> List[str]:
        """Parse generated code to find HTML filenames before execution."""
        html_files = []
        try:
            pattern1 = r'\.write_html\s*\(\s*["\']([^"\']+\.html)["\']'
            matches1 = re.findall(pattern1, code, re.IGNORECASE | re.UNICODE)
            
            lines = code.split('\n')
            var_to_file = {}
            
            for line in lines:
                match = re.search(r'(\w+)\s*=\s*["\']([^"\']+\.html)["\']', line, re.IGNORECASE)
                if match:
                    var_name, file_name = match.groups()
                    var_to_file[var_name] = file_name
            
            for line in lines:
                match = re.search(r'\.write_html\s*\(\s*(\w+)\s*\)', line)
                if match:
                    var_name = match.group(1)
                    if var_name in var_to_file:
                        html_files.append(var_to_file[var_name])
            
            html_files.extend(matches1)
            
            seen = set()
            unique_files = []
            for f in html_files:
                filename = f.split('/')[-1].split('\\')[-1]
                if filename not in seen and filename.endswith('.html'):
                    seen.add(filename)
                    unique_files.append(filename)
            
            if unique_files:
                logger.debug(f"Extracted {len(unique_files)} HTML file(s) from code: {unique_files}")
            
        except Exception as e:
            logger.error(f"Error extracting HTML files from code: {e}", exc_info=True)
        
        return unique_files
    
    def _verify_html_files_exist(self, expected_files: List[str], output_dir: Path, max_retries: int = 5) -> List[str]:
        """Verify expected HTML files exist after execution with retries."""
        if not expected_files:
            return []
        
        verified = []
        for attempt in range(max_retries):
            verified = []
            for filename in expected_files:
                file_path = output_dir / filename
                try:
                    if file_path.exists() and file_path.stat().st_size > 0 and file_path.suffix.lower() == '.html':
                        verified.append(filename)
                except Exception as e:
                    logger.debug(f"Error checking file {filename}: {e}")
            
            if len(verified) == len(expected_files):
                break
            
            if attempt < max_retries - 1:
                time.sleep(0.3)
        
        if len(verified) < len(expected_files):
            missing = set(expected_files) - set(verified)
            logger.warning(f"Some expected HTML files not found: {missing}")
        
        return verified
    
    def _extract_html_files_from_output(self, output: str, output_dir: Path) -> List[str]:
        """Extract HTML filenames from execution output text."""
        html_files = []
        try:
            patterns = [
                r'([\w\-_\u4e00-\u9fff]+\.html)',
                r'["\']([^"\']+\.html)["\']',
                r'saved\s+(?:to|as|in)\s+["\']?([^"\'\s]+\.html)["\']?',
                r'written\s+(?:to|as|in)\s+["\']?([^"\'\s]+\.html)["\']?',
                r'Chart\s+saved\s+to\s+["\']?([^"\'\s]+\.html)["\']?',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, output, re.IGNORECASE)
                for match in matches:
                    file_path = output_dir / match
                    if file_path.exists() and file_path.suffix.lower() == '.html':
                        html_files.append(match)
            
            if html_files:
                logger.debug(f"Found HTML files in output: {html_files}")
                
        except Exception as e:
            logger.error(f"Error extracting HTML files from output: {e}")
        
        return html_files


