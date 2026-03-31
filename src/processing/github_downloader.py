import os
import urllib.request
import zipfile
import shutil
import logging

logger = logging.getLogger(__name__)

class GithubDownloader:
    def __init__(self, target_dir="data/repos"):
        self.target_dir = target_dir
        os.makedirs(self.target_dir, exist_ok=True)
        
    def download_repo(self, repo_url: str) -> str:
        """Downloads a GitHub repository as a ZIP archive and returns the path."""
        repo_url = repo_url.rstrip('/')
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
            
        repo_name = repo_url.split('/')[-1]
        extract_path = os.path.join(self.target_dir, repo_name)
        
        # Check if already downloaded
        if os.path.exists(extract_path) and os.path.isdir(extract_path):
            existing_contents = os.listdir(extract_path)
            if len(existing_contents) > 0:
                logger.info(f"Repo {repo_name} already exists. Skipping download.")
                
                # If there's exactly one folder (e.g. minbpe-master), dive into it
                if len(existing_contents) == 1 and os.path.isdir(os.path.join(extract_path, existing_contents[0])):
                    return os.path.join(extract_path, existing_contents[0])
                return extract_path
                
        zip_url_main = f"{repo_url}/archive/refs/heads/main.zip"
        zip_url_master = f"{repo_url}/archive/refs/heads/master.zip"
        zip_path = os.path.join(self.target_dir, f"{repo_name}.zip")
        
        # Download ZIP
        try:
            logger.info(f"Attempting to download repository from {zip_url_main}")
            req = urllib.request.Request(zip_url_main, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        except Exception:
            try:
                logger.info(f"main.zip failed. Trying {zip_url_master}")
                req = urllib.request.Request(zip_url_master, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            except Exception as e:
                logger.error(f"Failed to download zip from both main and master: {e}")
                return ""
                
        # Extract ZIP
        try:
            logger.info(f"Extracting {zip_path} to {extract_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            os.remove(zip_path)
            
            # Repos usually extract to a subfolder like minbpe-master
            extracted_subdirs = os.listdir(extract_path)
            if len(extracted_subdirs) == 1 and os.path.isdir(os.path.join(extract_path, extracted_subdirs[0])):
                return os.path.join(extract_path, extracted_subdirs[0])
                
            return extract_path
        except Exception as e:
            logger.error(f"Failed to extract zip: {e}")
            return ""
