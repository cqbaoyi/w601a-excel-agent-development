"""Code execution module for safely executing generated Python code."""

import logging
from typing import Dict, Optional, Tuple

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
            Dictionary with 'output' and 'error' keys
        """
        kernel_manager = None
        client = None
        
        try:
            # Create new kernel
            kernel_manager, client = start_new_kernel()
            logger.info("Jupyter kernel started")
            
            # Prepare code with file path context
            full_code = self._prepare_code(code, file_path)
            
            # Execute code
            client.execute(full_code)
            
            # Get output
            output, error = self._capture_output(client)
            
            return {
                "output": output,
                "error": error,
                "success": error is None
            }
            
        except Exception as e:
            logger.error(f"Error executing code: {e}", exc_info=True)
            return {
                "output": "",
                "error": f"Execution failed: {str(e)}",
                "success": False
            }
            
        finally:
            # Clean up resources
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
        """
        Prepare code for execution by adding necessary context.
        
        Args:
            code: Original code
            file_path: Path to Excel file
            
        Returns:
            Prepared code string
        """
        import os
        from pathlib import Path
        
        # Convert file_path to absolute path to avoid issues when changing working directory
        abs_file_path = Path(file_path).absolute()
        
        # Verify file exists before execution
        if not abs_file_path.exists():
            logger.error(f"Excel file not found: {abs_file_path}")
            logger.error(f"Original path provided: {file_path}")
            raise FileNotFoundError(f"Excel file not found: {abs_file_path}. Original path: {file_path}")
        
        # Set up output directory for generated files (charts, etc.)
        output_dir = Path(__file__).parent.parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Ensure file_path and output_dir are available in the execution context
        # Use str() to handle Windows paths properly - escape backslashes
        abs_file_path_str = str(abs_file_path).replace('\\', '\\\\')  # Escape backslashes for Windows
        
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
                    # Standard output
                    text = content.get('text', '')
                    if text:
                        output_lines.append(text)
                        
                elif msg_type == 'execute_result':
                    # Execution result
                    if 'text/plain' in content.get('data', {}):
                        output_lines.append(content['data']['text/plain'])
                        
                elif msg_type == 'error':
                    # Error occurred
                    traceback = content.get('traceback', [])
                    error = '\n'.join(traceback)
                    logger.error(f"Code execution error: {error}")
                    break
                    
                elif msg_type == 'status':
                    # Check if execution is complete
                    if content.get('execution_state') == 'idle':
                        break
                        
            except Exception as e:
                logger.error(f"Error capturing output: {str(e)}")
                break
        
        output = '\n'.join(output_lines) if output_lines else "No output"
        return output, error


