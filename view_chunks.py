import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from storage.vector_store import VectorStoreManager

def export_all_chunks():
    manager = VectorStoreManager()
    
    # Get EVERYTHING from the ChromaDB collection
    result = manager.vector_store.get()
    
    if not result or not result.get('documents'):
        print("Vector DB is empty. No chunks to dump!")
        return
        
    documents = result['documents']
    metadatas = result['metadatas']
    ids = result['ids']
    
    output_data = []
    for doc_id, doc, meta in zip(ids, documents, metadatas):
        output_data.append({
            "id": doc_id,
            "metadata": meta,
            "content": doc
        })
        
    dump_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_chunks_dump.json")
    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"SUCCESS: Dumped {len(output_data)} chunks to {dump_path}")

if __name__ == "__main__":
    export_all_chunks()
