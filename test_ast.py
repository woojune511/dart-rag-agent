import sys
import os

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from processing.github_downloader import GithubDownloader
from processing.ast_parser import ASTParser

if __name__ == "__main__":
    downloader = GithubDownloader()
    ast_parser = ASTParser()

    repo_url = "https://github.com/karpathy/minbpe"
    print(f"Downloading {repo_url}...")
    repo_path = downloader.download_repo(repo_url)
    print(f"Downloaded to {repo_path}")

    print("Parsing AST...")
    chunks = ast_parser.process_repo(repo_path)
    print(f"Parsed {len(chunks)} chunks.")
    if chunks:
        print(f"First chunk preview:\n{chunks[0].content[:200]}")
