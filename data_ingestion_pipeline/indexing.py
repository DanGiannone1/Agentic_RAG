import logging
import os
import hashlib
import base64
from typing import List, Dict, Any
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from chunking import recursive_character_chunking_langchain
import fitz  # PyMuPDF
import json
from datetime import datetime, timezone
from langchain_openai import AzureOpenAIEmbeddings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress Azure SDK logging
logging.getLogger('azure').setLevel(logging.ERROR)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)

# Load environment variables
load_dotenv()

# Azure Configuration
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_ACCOUNT_KEY = os.environ.get("STORAGE_ACCOUNT_KEY")
STORAGE_ACCOUNT_CONTAINER = os.environ.get("STORAGE_ACCOUNT_CONTAINER", "documents")
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

def validate_base64(string: str) -> bool:
    """Validate if a string is base64 encoded."""
    try:
        if string is None:
            return False
        # Check if the string has valid base64 length
        if len(string) % 4 != 0:
            return False
        # Try to decode
        base64.b64decode(string)
        return True
    except Exception:
        return False

def validate_azure_credentials():
    """Validate Azure credentials from environment variables."""
    required_vars = {
        "Storage Account Name": STORAGE_ACCOUNT_NAME,
        "Storage Account Key": STORAGE_ACCOUNT_KEY,
        "Storage Container": STORAGE_ACCOUNT_CONTAINER,
        "Search Endpoint": AI_SEARCH_ENDPOINT,
        "Search Key": AI_SEARCH_KEY,
        "Search Index": AI_SEARCH_INDEX,
        "OpenAI Endpoint": aoai_endpoint,
        "OpenAI Key": aoai_key
    }

    missing_vars = [name for name, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    if not validate_base64(STORAGE_ACCOUNT_KEY):
        raise ValueError("Storage Account Key is not a valid base64-encoded string")

class DocumentProcessor:
    def __init__(self):
        """Initialize the document processor with necessary clients."""
        try:
            validate_azure_credentials()
            
            self.blob_service_client = BlobServiceClient(
                account_url=f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
                credential=STORAGE_ACCOUNT_KEY
            )
            self.search_client = SearchClient(
                AI_SEARCH_ENDPOINT,
                AI_SEARCH_INDEX,
                AzureKeyCredential(AI_SEARCH_KEY)
            )
            
            # Verify connection to blob storage
            self.blob_service_client.get_service_properties()
            logger.info("Successfully connected to Azure Blob Storage")
            
            # Load or create document metadata
            self.metadata_file = 'doc_metadata.json'
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    metadata_list = json.load(f)
            else:
                metadata_list = []
                with open(self.metadata_file, 'w') as f:
                    json.dump(metadata_list, f)
            self.document_metadata = {doc["id"]: doc for doc in metadata_list}
            
        except Exception as e:
            logger.error(f"Failed to initialize DocumentProcessor: {str(e)}")
            raise

    def process_document(self, blob_name: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        """
        Process a single document from Azure Blob Storage:
        1. Read the PDF document
        2. Chunk the content while maintaining page numbers
        3. Upload chunks to the search index
        """
        print(f"Processing document: {blob_name}")
        
        # Get document metadata
        doc_metadata = self.document_metadata.get(blob_name, {})
        category = doc_metadata.get("category", "unknown")
        sensitivity_label = doc_metadata.get("sensitivity_label", "internal")
        
        # Generate blob URL
        blob_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{STORAGE_ACCOUNT_CONTAINER}/{blob_name}"
        
        # Read PDF document from Azure Blob Storage
        blob_client = self.blob_service_client.get_blob_client(container=STORAGE_ACCOUNT_CONTAINER, blob=blob_name)
        pdf_data = blob_client.download_blob().readall()
        
        # Extract text with page numbers
        full_text = ""
        with fitz.open(stream=pdf_data, filetype="pdf") as doc:
            page_number = 1
            for page in doc:
                page_text = page.get_text()
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
        """Process all documents in the configured Azure Blob Storage container."""
        container_client = self.blob_service_client.get_container_client(STORAGE_ACCOUNT_CONTAINER)
        
        for blob in container_client.list_blobs():
            try:
                self.process_document(blob.name)
            except Exception as e:
                print(f"Error processing document {blob.name}: {str(e)}")
                continue

def main():
    """Main function to run the document processing pipeline."""
    try:
        processor = DocumentProcessor()
        processor.process_all_documents()
    except Exception as e:
        logger.error(f"Error in main processing pipeline: {str(e)}")
        raise

if __name__ == "__main__":
    main()