"""
This module handles document processing operations using Azure Blob Storage.
It provides functionality to upload documents to Blob Storage.

Prerequities:
     Create an Azure Blob Storage account and container.
     Update the env file with below details
        STORAGE_ACCOUNT_NAME="<Enter your storage account name>"
        STORAGE_ACCOUNT_CONTAINER="<Enter your container name>"
        SAMPLE_DOCUMENT_FILE_PATH="<Enter your sample document file path>"
    Grant the necessary permissions to the Azure Blob Storage account. 
        Add the "Storage Blob Data Contributor" role to the service principal or managed identity.   
    Execute the requirnment.txt file to install the required packages
        azure-storage-blob==12.22.0    
Validations:
    Once you run this program, login to Azure portal and check the container for the uploaded files.

"""

# Suppress Azure SDK logging
import logging
logging.getLogger('azure').setLevel(logging.ERROR)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)

import os
from typing import Union, Dict, Any, List
from functools import wraps
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient  # Updated import
from azure.ai.documentintelligence.models import AnalyzeResult


import io
from azure.identity import DefaultAzureCredential

# Load environment variables
load_dotenv()

# Azure Blob Storage Configuration
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_ACCOUNT_CONTAINER = os.environ.get("STORAGE_ACCOUNT_CONTAINER", "documents")
SAMPLE_DOCUMENT_FILE = os.environ.get("SAMPLE_DOCUMENT_FILE")
SAMPLE_DOCUMENT_FILE_PATH = os.environ.get("SAMPLE_DOCUMENT_FILE_PATH")

# Azure Document Intelligence Configuration
DOCUMENT_INTELLIGENCE_ENDPOINT = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOCUMENT_INTELLIGENCE_KEY = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")


def azure_error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper

def validate_storage_credentials():
    """Validate storage credentials and return the appropriate client parameters."""
    conn_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
    account_key = os.environ.get("STORAGE_ACCOUNT_KEY")
    
    if conn_string and "AccountName" in conn_string and "AccountKey" in conn_string:
        return {"connection_string": conn_string}
    elif account_name and account_key:
        account_url = f"https://{account_name}.blob.core.windows.net"
        return {"account_url": account_url, "credential": account_key}
    else:
        raise ValueError(
            "Either a valid connection string or account name/key pair must be provided. "
            "Please check your environment variables."
        )

@azure_error_handler
def get_blob_service_client() -> BlobServiceClient:
    """
    Create and return an Azure Blob Service Client using connection string.

    Returns
    -------
    BlobServiceClient
        An instance of the Azure Blob Service Client.

    Raises
    ------
    ValueError
        If the Azure Storage connection string is missing.
    """
    try:
        params = validate_storage_credentials()
        if "connection_string" in params:
            return BlobServiceClient.from_connection_string(params["connection_string"])
        else:
            return BlobServiceClient(params["account_url"], credential=params["credential"])
    except Exception as e:
        logging.error(f"Failed to create blob service client: {str(e)}")
        raise


@azure_error_handler
def upload_to_blob(file_content: Union[bytes, io.IOBase], filename: str, container_name: str = None) -> Dict[str, str]:
    """
    Upload a file to Azure Blob Storage.

    Parameters
    ----------
    file_content : Union[bytes, io.IOBase]
        The content of the file to upload. This can be either:
        - bytes: Raw file content (e.g., result of reading a file in binary mode)
        - io.IOBase: A file-like object (e.g., an open file handle)
    filename : str
        The name to give the file in Blob Storage.
    container_name : str, optional
        The name of the container to upload to. 
        If not provided, uses the default container from environment variables.

    Returns
    -------
    Dict[str, str]
        A dictionary containing:
        - 'message': A success message
        - 'blob_url': The URL of the uploaded blob

    Raises
    ------
    Exception
        If there's an error during the upload process.
    """
    blob_service_client = get_blob_service_client()
    container_name = container_name or STORAGE_ACCOUNT_CONTAINER
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(filename)
    
    if isinstance(file_content, io.IOBase):
        blob_client.upload_blob(file_content.read(), overwrite=True)
    else:
        blob_client.upload_blob(file_content, overwrite=True)
    
    print(f"File {filename} uploaded successfully")
    return {"message": f"File {filename} uploaded successfully", "blob_url": blob_client.url}


def upload_all_files_blob(local_folder_path: str, container_name: str) -> None:
    """
    Upload all PDF files from the local folder path to Azure Blob Storage container.

    Parameters
    ----------
    local_folder_path : str
        The local folder path containing PDF files to upload.
    container_name : str
        The name of the container to upload to.
    """
    # Get container client
    blob_service_client = get_blob_service_client()
    container_name = container_name or STORAGE_ACCOUNT_CONTAINER
    container_client = blob_service_client.get_container_client(container_name)
    
    # Iterate over all files in the local folder path
    for filename in os.listdir(local_folder_path):
        if filename.endswith(".pdf"):
            file_path = os.path.join(local_folder_path, filename)
            blob_client = container_client.get_blob_client(filename)
            
            # Read the file content and upload to Azure Blob Storage
            with open(file_path, "rb") as file:
                blob_client.upload_blob(file, overwrite=True)
            
            print(f"File {filename} uploaded successfully")


@azure_error_handler
def get_document_intelligence_client() -> DocumentIntelligenceClient:
    """
    Create and return an Azure Document Intelligence Client using key authentication.

    Returns
    -------
    DocumentIntelligenceClient
        An instance of the Azure Document Intelligence Client.

    Raises
    ------
    ValueError
        If the Document Intelligence configuration is missing.
    """
    endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )
    return document_intelligence_client


@azure_error_handler
def analyze_document(filename: str) -> AnalyzeResult:
    """
    Analyze a document using Azure Document Intelligence.

    Parameters
    ----------
    filename : str
        The name of the file in Blob Storage to analyze.

    Returns
    -------
    AnalyzeResult
        The result of the document analysis.

    Raises
    ------
    Exception
        If there's an error during the analysis process.
    """
    document_intelligence_client = get_document_intelligence_client()
    blob_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{STORAGE_ACCOUNT_CONTAINER}/{filename}"

    print(f"Analyzing document from blob storage: {blob_url}")
    analyze_request = {"urlSource": blob_url}
    poller = document_intelligence_client.begin_analyze_document("prebuilt-layout", analyze_request=analyze_request)
    result: AnalyzeResult = poller.result()
    print("Successfully read the document from blob storage with doc intelligence and extracted text.")
    return result

def run_examples():
    """Example usage of the document processing functions."""
    print("Uploading local file...")
    #Single PDF file upload scenario
    #path/to/your/sample/document.pdf    
    # Local file upload scenario
    
    #with open(SAMPLE_DOCUMENT_FILE, 'rb') as file:
    #    upload_result = upload_to_blob(file, os.path.basename(SAMPLE_DOCUMENT_FILE))
    #print(f"Local file upload: {upload_result['message']}")

    #All PDF files in a folder upload scenario
    upload_all_files_blob(SAMPLE_DOCUMENT_FILE_PATH, STORAGE_ACCOUNT_CONTAINER)
    print("All PDF files uploaded successfully.")
    
      

if __name__ == "__main__":
    run_examples()
