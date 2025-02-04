from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters import TokenTextSplitter
from langchain_openai.embeddings import AzureOpenAIEmbeddings

import os
import tiktoken
from dotenv import load_dotenv

load_dotenv()

# Azure OpenAI configuration
aoai_deployment = os.getenv("AOAI_DEPLOYMENT")
aoai_key = os.getenv("AOAI_KEY")
aoai_endpoint = os.getenv("AOAI_ENDPOINT")

#Embeddings model
embeddings_model = AzureOpenAIEmbeddings(
    model="text-embedding-ada-002",
    azure_endpoint=aoai_endpoint,
    openai_api_key=aoai_key
)

encoding = tiktoken.encoding_for_model("gpt-4o")

def num_tokens_from_string(string):
    return len(encoding.encode(string))

def semantic_chunking_langchain(full_text):
    breakpoint_type = "interquartile"
    
    text_splitter = SemanticChunker(embeddings_model, breakpoint_threshold_type=breakpoint_type)
    chunks = text_splitter.split_text(full_text)
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
    # Get token count of the full_text
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

def run_examples():
    # Instead of reading from a file, you would pass the text directly
    sample_text = "Your sample text goes here..."
    
    # Choose one of the functions to run
    chunks = semantic_chunking_langchain(sample_text)
    # chunks = chunk_by_tokens_langchain(sample_text)
    # chunks = recursive_character_chunking_langchain(sample_text)
    
    print(f"Total chunks returned: {len(chunks)}")

# Run the examples
if __name__ == "__main__":
    run_examples()