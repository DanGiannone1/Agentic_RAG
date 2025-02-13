# Data Pipeline Implementations:


This folder contains implmentation of Data Ingestion pipleine for Agentic RAG.


Its the Pre-requities before you start setting up Agentic RAG, it helps you to get your Data uploaded to Azure Blob storage, creates chunking, embedding, create Azure AI Search Index and perform the Indexing for the Search Index.


In case you have completed these steps, you can follow the setup instructions in the respective implementation directories:
   - [Document Search Setup](./agentic_doc_chunk_rag/agentic_doc_chunk_rag.md#setup--usage)
   - [NL2SQL Setup](./nl2sql/agentic_nl2sql.md#setup--usage)



# 🔍 The RAG Flow: From Data to Insights:

📂 Documents → 📑 Chunks → 📏 Embedding Model → 📚 Vector Database → 📝 Prompt Template → 🤖 LLM

# Implementation Summaries:


### Document Processing
This module handles document processing operations using Azure Blob Storage. It provides functionality to upload documents to Blob Storage.

### Chunking
This module is designed to demonstrate different methods for splitting large text documents into smaller, manageable chunks.

### Create Index
This module creates a search index in Azure Cognitive Search (formerly Azure AI Search) with specific field definitions and vector search capabilities.

### Indexing
This module combines document processing, chunking, and indexing functionality. It processes documents from Azure Data Lake Storage using Document Intelligence,
chunks them while maintaining page context, and uploads to Azure Cognitive Search.


# Implementation Details:

The below section explains about implementation details, Prerequities, configuration details required to execute these steps and how to validate the putput.


### 1. **Document Processing**:

document_processing.py file handles document processing operations using Azure Blob Storage.
It provides functionality to upload documents to Blob Storage.

**Prerequities:**

     * Create an Azure Blob Storage account and container.
     * Update the env file with below details
        STORAGE_ACCOUNT_NAME="<Enter your storage account name>"
        STORAGE_ACCOUNT_CONTAINER="<Enter your container name>"
        SAMPLE_DOCUMENT_FILE_PATH="<Enter your sample document file path>"
     * Grant the necessary permissions to the Azure Blob Storage account. 
        Add the "Storage Blob Data Contributor" role to the service principal or managed identity.   
     * Execute the requirnment.txt file to install the required packages
        azure-storage-blob==12.22.0    

**Validations:**

    Once you run this program, login to Azure portal and check the container for the uploaded files.

### 2. **Chunking**:

This Chunking.py file is designed to demonstrate different methods for splitting large text documents into smaller, manageable chunks. This is particularly useful for processing and analyzing large texts, such as PDFs, in a more efficient manner. Here’s a summary of the file and its importance:
This code is for your understanding and Chunking startegy is implemented during the process of Indexing (Step#4: Indexing)

This file demostrates below 3 types of chunking.

**1. Semantic Chunking:**

**Description:** This method uses sentence embeddings to find breakpoints in the text where the semantic similarity between sentences drops below a certain threshold.
**Implementation:** Sentences are split based on semantic similarity, ensuring that each chunk maintains a coherent meaning.
**Use Case:** Useful for tasks where maintaining the semantic integrity of the text is crucial.

**2. Token-Based Chunking:**

**Description:** This method splits the text based on the number of tokens, ensuring that each chunk contains a specified number of tokens with some overlap.
**Implementation:** Uses the TokenTextSplitter from Langchain to split the text into chunks of a specified token size.
**Use Case:** Ideal for tasks where the text needs to be processed in fixed-size chunks, such as feeding into language models.

**3. Recursive Character Chunking:**

**Description:** This method recursively splits the text based on character count, ensuring that each chunk is within a specified character limit with some overlap.
**Implementation:** Uses the RecursiveCharacterTextSplitter to split the text into chunks based on character length.
**Use Case:** Suitable for tasks where the text needs to be split based on character count, such as preparing text for display or storage.

**Prerequities:**

     * Update the env file with below details
        SAMPLE_DOCUMENT_FILE_PATH="<your Local Folder Path>/documents/<FileName>.pdf"
        CHUNKED_DOCUMENT_FILE_PATH="<your Local Folder Path>/documents/chunked/"   
     
     * Execute the requirnment.txt file to install the required packages
        pip install langchain
        pip install langchain-openai
        pip install langchain-community   
        pip install pymupdf numpy scikit-learn

**Validations:**

    Once you run this program, Explore chunked folder for chunked data.


### 3. **Create Index**:

create_index.py file creates a search index in Azure Cognitive Search (formerly Azure AI Search) with specific field definitions and vector search capabilities.

**Prerequities:**

     * Create Azure AI Search https://learn.microsoft.com/en-us/azure/search/search-create-service-portal

     * Update the env file with below details
        AZURE_SEARCH_ENDPOINT="<Update Azure AI Search Endpoint>"
        AZURE_SEARCH_KEY="<Update Azure AI Search Key>"   
     
             

**Validations:**

    Once you run this program, Go to Azure portal to validate Index created.



### 4. **Indexing**:
This module combines document processing, chunking, and indexing functionality.
It processes documents from Azure Blob Storage using Document Intelligence,
chunks them while maintaining page context, and uploads to Azure AI Search.


**Prerequities:**

     Update the env file with below details
        SAMPLE_DOCUMENT_FILE_PATH="<your Local Folder Path>/documents/<FileName>.pdf"
        CHUNKED_DOCUMENT_FILE_PATH="<your Local Folder Path>/documents/chunked/"   
     
     Execute the requirnment.txt file to install the required packages
        pip install langchain
        pip install langchain-openai
        pip install langchain-community   
        pip install pymupdf numpy scikit-learn

**Validations:**

    Once you run this program, Explore chunked folder for chunked data.



# Data Ingestion Pipeline Folder Structure

This folder has below structure.
```plaintext
agentic-rag/
├── data_ingestion_pipeline/  
   ├── README.md                         # README file for data_ingestion_pipeline.
   ├── document_processing.py            # Functionality to upload documents to Blob Storage.
   ├── chunking.py                       # Demostration on Chunking strategies.
   ├── create-index.py                   # Creates Indexs.
   ├── indexing.py                       # Functionality for document processing, chunking, and indexing.
├── documents/                           # Place your sample documents    
```

# Why Data Pipeline?







## Architecture Overview

TBD...

## Getting Started

Once you have completed all the above steps, its now time to set up your implmenetation, refer below section.


1. Choose the implementation that matches your use case:
   - Use **Document Search** for unstructured document retrieval and synthesis
    - Use **NL2SQL** for structured database querying with natural language

2. Follow the setup instructions in the respective implementation directories:
   - [Document Search Setup](./agentic_doc_chunk_rag/agentic_doc_chunk_rag.md#setup--usage)
   - [NL2SQL Setup](./nl2sql/agentic_nl2sql.md#setup--usage)


