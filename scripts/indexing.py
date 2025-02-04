"""
This module combines document processing, chunking, and indexing functionality.
It processes documents from Azure Data Lake Storage using Document Intelligence,
chunks them while maintaining page context, and uploads to Azure Cognitive Search.
"""

# Suppress Azure SDK logging
import logging
logging.getLogger('azure').setLevel(logging.ERROR)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)

import os
import hashlib
from typing import List, Dict, Any
from dotenv import load_dotenv
from document_processing import get_document_intelligence_client, get_blob_service_client
from chunking import recursive_character_chunking_langchain
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.storage.blob import BlobServiceClient
import json
from datetime import datetime, timezone
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

# Load environment variables
load_dotenv()

# Azure Configuration
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_ACCOUNT_CONTAINER = os.environ.get("STORAGE_ACCOUNT_CONTAINER")
AI_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT")
AI_SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY")
AI_SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX")

aoai_endpoint = os.environ.get("AOAI_ENDPOINT")
aoai_key = os.environ.get("AOAI_KEY")

embeddings_model = AzureOpenAIEmbeddings(
    azure_deployment="text-embedding-3-large",
    api_key=aoai_key,
    azure_endpoint=aoai_endpoint
)

class DocumentProcessor:
    def __init__(self):
        """Initialize the document processor with necessary clients."""
        self.doc_intelligence_client = get_document_intelligence_client()
        self.blob_service_client = get_blob_service_client()
        self.search_client = SearchClient(
            AI_SEARCH_ENDPOINT,
            AI_SEARCH_INDEX,
            AzureKeyCredential(AI_SEARCH_KEY)
        )
        # Load document metadata
        with open('auxilium_doc_metadata.json', 'r') as f:
            metadata_list = json.load(f)
            print("\nLoaded document metadata:")
            for doc in metadata_list:
                print(f"Document: {doc['id']}")
                print(f"Category: {doc['category']}")
                print(f"Sensitivity: {doc['sensitivity_label']}\n")
            self.document_metadata = {doc["id"]: doc for doc in metadata_list}

    def process_document(self, blob_name: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        """
        Process a single document from ADLS:
        1. Analyze with Document Intelligence
        2. Chunk the content while maintaining page numbers
        3. Upload chunks to the search index
        """
        print(f"Processing document: {blob_name}")
        
        # Get document metadata
        print(f"\nAvailable document IDs in metadata: {list(self.document_metadata.keys())}")
        print(f"Looking up metadata for file: {blob_name}")
        doc_metadata = self.document_metadata.get(blob_name, {})
        print(f"Found metadata: {doc_metadata}")
        category = doc_metadata.get("category", "unknown")
        sensitivity_label = doc_metadata.get("sensitivity_label", "internal")
        
        # Generate blob URL
        blob_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{STORAGE_ACCOUNT_CONTAINER}/{blob_name}"
        
        # Analyze document with Document Intelligence
        print("Analyzing document with Document Intelligence")
        analyze_request = {"urlSource": blob_url}
        poller = self.doc_intelligence_client.begin_analyze_document("prebuilt-layout", analyze_request=analyze_request)
        result = poller.result()

        # Extract text with page numbers
        full_text = ""
        page_number = 1
        for page in result.pages:
            page_text = ""
            for line in page.lines:
                page_text += line.content + "\n"
            # Add page marker at the end of each page
            page_text += f'###Page Number: {page_number}###\n\n'
            full_text += page_text
            page_number += 1

        # Chunk the document
        print("Chunking document")
        chunks = recursive_character_chunking_langchain(full_text)

        # Process and upload chunks
        documents = []
        current_page = 1
        
        for i, chunk in enumerate(chunks):
            # Find page numbers in chunk
            page_numbers = []
            lines = chunk.split('\n')
            for line in lines:
                if '###Page Number:' in line:
                    try:
                        page_num = int(line.split('###Page Number:')[1].split('###')[0].strip())
                        page_numbers.append(page_num)
                    except ValueError:
                        continue

            # Determine page range for chunk
            if page_numbers:
                chunk_start_page = page_numbers[0]
                chunk_end_page = page_numbers[-1] if len(page_numbers) > 1 else page_numbers[0]
                current_page = chunk_end_page
            else:
                chunk_start_page = current_page
                chunk_end_page = current_page

            # Generate unique ID for chunk
            chunk_id = hashlib.md5((blob_name + str(i)).encode()).hexdigest()

            # Generate vector embedding for chunk
            try:
                content_vector = embeddings_model.embed_query(chunk)
            except Exception as e:
                print(f"Error generating vector embedding for chunk {chunk_id} in {blob_name}: {str(e)}")
                continue

            # Create document for indexing with metadata
            document = {
                "id": chunk_id,
                "source_file": blob_name,
                "source_pages": [p for p in range(chunk_start_page, chunk_end_page + 1)],
                "content": chunk,
                "content_vector": content_vector,
                "category": category,
                "sensitivity_label": sensitivity_label,
                "created_date": datetime.now(timezone.utc).isoformat()
            }
            documents.append(document)

        # Upload chunks to search index
        print(f"Uploading {len(documents)} chunks to search index")
        self.search_client.upload_documents(documents)
        print(f"Successfully processed and indexed document: {blob_name}")

    def process_all_documents(self) -> None:
        """Process all documents in the configured ADLS container."""
        container_client = self.blob_service_client.get_container_client(STORAGE_ACCOUNT_CONTAINER)
        
        for blob in container_client.list_blobs():
            try:
                self.process_document(blob.name)
            except Exception as e:
                print(f"Error processing document {blob.name}: {str(e)}")
                continue

def main():
    """Main function to run the document processing pipeline."""
    processor = DocumentProcessor()
    processor.process_all_documents()

if __name__ == "__main__":
    main()
