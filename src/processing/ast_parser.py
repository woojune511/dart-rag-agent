import ast
import os
import logging
from typing import List, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CodeChunk(BaseModel):
    content: str
    metadata: Dict[str, Any]

class ASTParser:
    def __init__(self):
        pass

    def parse_file(self, filepath: str, repo_name: str) -> List[CodeChunk]:
        """Parses a Python file into Semantic chunks based on AST Class and Function definitions."""
        chunks = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            
            tree = ast.parse(source)
            lines = source.splitlines()
            
            for node in ast.walk(tree):
                # Extract Class and Function nodes
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_lineno = node.lineno - 1
                    # Fallback to start_line if end_lineno is missing in older Python AST implementations
                    end_lineno = getattr(node, "end_lineno", start_lineno + 1)
                    
                    block_code = "\n".join(lines[start_lineno:end_lineno])
                    node_type = "class" if isinstance(node, ast.ClassDef) else "function"
                    
                    meta = {
                        "repo": repo_name,
                        "file_path": filepath,
                        "node_type": node_type,
                        "node_name": node.name
                    }
                    
                    # Store entire block in an annotated markdown format
                    content = f"File: {filepath}\nType: {node_type}\nName: {node.name}\nSource Code:\n```python\n{block_code}\n```"
                    chunks.append(CodeChunk(content=content, metadata=meta))
                    
        except SyntaxError:
            logger.warning(f"Syntax error trying to parse {filepath}")
        except Exception as e:
            logger.warning(f"Failed to parse {filepath}: {e}")
            
        return chunks
        
    def process_repo(self, repo_path: str) -> List[CodeChunk]:
        """Walks an entire repository and chunks all Python files."""
        repo_name = os.path.basename(repo_path)
        all_chunks = []
        
        for root, _, files in os.walk(repo_path):
            # Skip hidden elements, tests, and caches
            if any(skip in root for skip in [".git", "__pycache__", "venv", ".venv", "tests"]):
                continue
                
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    chunks = self.parse_file(filepath, repo_name)
                    all_chunks.extend(chunks)
                    
        logger.info(f"Successfully extracted {len(all_chunks)} AST block chunks from {repo_name}")
        return all_chunks
