

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters import TokenTextSplitter
#pip install langchain
#pip install langchain-openai
#pip install langchain-community


from langchain_openai.embeddings import AzureOpenAIEmbeddings
import os
import tiktoken
from dotenv import load_dotenv

import fitz  # PyMuPDF
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

#pip install pymupdf numpy scikit-learn
#pip install pymupdf

load_dotenv()

# Azure OpenAI configuration
aoai_deployment = os.getenv("AOAI_DEPLOYMENT")
aoai_key = os.getenv("AOAI_KEY")
aoai_endpoint = os.getenv("AOAI_ENDPOINT")
aoai_embedding_model = os.getenv("AOAI_EMBEDDING_MODEL")

sample_pdf_path = os.getenv("SAMPLE_DOCUMENT_FILE_PATH")
chunked_doc_file = os.getenv("CHUNKED_DOCUMENT_FILE_PATH")


#Embeddings model
embeddings_model = AzureOpenAIEmbeddings(
    model=aoai_embedding_model,
    azure_endpoint=aoai_endpoint,
    openai_api_key=aoai_key
)

encoding = tiktoken.encoding_for_model(aoai_deployment)

def num_tokens_from_string(string):
    return len(encoding.encode(string))

class SemanticChunker:
    def __init__(self, embeddings_model, breakpoint_threshold=0.8):
        self.embeddings_model = embeddings_model
        self.breakpoint_threshold = breakpoint_threshold

    def split_text(self, text, chunk_size=1000, overlap=100):
        sentences = text.split('. ')
        embeddings = self.embeddings_model.embed_documents(sentences)
        breakpoints = self.find_breakpoints(embeddings)
        
        chunks = []
        start = 0
        for breakpoint in breakpoints:
            end = breakpoint
            chunk = '. '.join(sentences[start:end])
            chunks.append(chunk)
            start = max(0, end - overlap)
        
        if start < len(sentences):
            chunks.append('. '.join(sentences[start:]))
        
        return chunks

    def find_breakpoints(self, embeddings):
        similarities = cosine_similarity(embeddings)
        breakpoints = []
        for i in range(1, len(similarities)):
            if similarities[i-1][i] < self.breakpoint_threshold:
                breakpoints.append(i)
        return breakpoints

def semantic_chunking_langchain(full_text):
    chunker = SemanticChunker(embeddings_model)
    chunks = chunker.split_text(full_text)
    total_tokens = 0
    
    for i, chunk in enumerate(chunks):
        token_count = num_tokens_from_string(chunk)
        length = len(chunk)
        print(f"******************Chunk {i}: Tokens: {token_count}******************")
        print(chunk)
        total_tokens += token_count
    
    return chunks

def chunk_by_tokens_langchain(full_text, chunk_size=1000, chunk_overlap=100):
    text_splitter = TokenTextSplitter(encoding_name='gpt2', chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    chunks = text_splitter.split_text(full_text)
    total_tokens = 0
    for chunk in chunks:
        token_count = num_tokens_from_string(chunk)
        total_tokens += token_count
    
    return chunks

def recursive_character_chunking_langchain(full_text):
    token_count = num_tokens_from_string(full_text)
    print(f"Number of tokens: {token_count}")
    print(f"Length of full text: {len(full_text)}")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2500,
        chunk_overlap=250,
        length_function=len,
        is_separator_regex=False,
    )
    texts = text_splitter.split_text(full_text)
    
    total_tokens = 0
    for chunk in texts:
        token_count = num_tokens_from_string(chunk)
        length = len(chunk)
        print(f"Tokens: {token_count}")
        total_tokens += token_count
    
    return texts

def save_chunks_to_local(chunks, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for i, chunk in enumerate(chunks):
        chunk_filename = os.path.join(output_dir, f"chunk_{i}.txt")
        with open(chunk_filename, 'w', encoding='utf-8') as f:
            f.write(chunk)
        print(f"Saved chunk {i} to {chunk_filename}")

def run_examples():
    #sample_pdf_path = 'path/to/your/sample/document.pdf'
    
    # Read the PDF file and extract text
    with fitz.open(sample_pdf_path) as doc:
        full_text = ""
        for page in doc:
            full_text += page.get_text()
    
    # Choose one of the functions to run
    chunks = semantic_chunking_langchain(full_text)
    #chunks = chunk_by_tokens_langchain(full_text)
    #chunks = recursive_character_chunking_langchain(full_text)
    
    # Save the chunks to a local directory
    output_dir = chunked_doc_file
    save_chunks_to_local(chunks, output_dir)

if __name__ == "__main__":
    run_examples()