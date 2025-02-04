# agentic_doc_chunk_rag.py
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from pydantic import BaseModel
from typing import List, Dict, Any, Union, Literal
from dotenv import load_dotenv
import os
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, TypedDict, Set
from langsmith import traceable

load_dotenv()

# Azure Search configuration
ai_search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
ai_search_key = os.environ["AZURE_SEARCH_KEY"]
ai_search_index = os.environ["AZURE_SEARCH_INDEX"]

# Azure OpenAI configuration
aoai_deployment = os.getenv("AOAI_DEPLOYMENT")
aoai_key = os.getenv("AOAI_KEY")
aoai_endpoint = os.getenv("AOAI_ENDPOINT")

search_client = SearchClient(ai_search_endpoint, ai_search_index, AzureKeyCredential(ai_search_key))
print("Index: ", ai_search_index)

MAX_ATTEMPTS = 3
NUM_SEARCH_RESULTS = 5
K_NEAREST_NEIGHBORS = 30

# Type Definitions
class SearchResult(TypedDict):
    id: str
    content: str
    sourceFileName: str
    sourcePages: int
    score: float

class ReviewDecision(BaseModel):
    """Schema for review agent decisions"""
    thought_process: str
    valid_results: List[int]  # Indices of valid results
    invalid_results: List[int]  # Indices of invalid results
    decision: Literal["retry", "finalize"]

class SearchPromptResponse(BaseModel):
    """Schema for search prompt responses"""
    search_query: str
    filter: str | None

class ChatState(TypedDict):
    """Complete state of the conversation"""
    user_input: str
    current_results: List[SearchResult]
    vetted_results: List[SearchResult]
    discarded_results: List[SearchResult]
    processed_ids: Set[str]  # Track all processed document IDs
    reviews: List[str]  # Thought processes from reviews
    decisions: List[str]  # Store the actual decisions
    final_answer: str | None
    attempts: int  # Track number of search attempts
    search_history: List[Dict[str, Any]]  # Track previous search queries and filters

# LLM Setup
llm = AzureChatOpenAI(
    azure_deployment=aoai_deployment,
    api_version="2024-05-01-preview",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=aoai_key,
    azure_endpoint=aoai_endpoint
)

review_llm = llm.with_structured_output(ReviewDecision)

embeddings_model = AzureOpenAIEmbeddings(
    azure_deployment="text-embedding-3-large",
    api_key=aoai_key,
    azure_endpoint=aoai_endpoint
)

def format_search_results(results: List[SearchResult]) -> str:
    """Format search results into a nicely formatted string.
    
    Args:
        results: List of SearchResult objects
        
    Returns:
        str: Formatted string containing all search results
    """
    output_parts = ["\n=== Search Results ==="]
    
    for i, result in enumerate(results, 1):
        result_parts = [
            f"\nResult #{i}",
            "=" * 80,
            f"ID: {result['id']}",
            f"Source File: {result['source_file']}",
            f"Source Pages: {result['source_pages']}",
            "\n<Start Content>",
            "-" * 80,
            result['content'],
            "-" * 80,
            "<End Content>"
        ]
        output_parts.extend(result_parts)
        
    
    # Join all parts with newlines
    formatted_output = "\n".join(output_parts)
    
    # For debugging, print a truncated version to console
    debug_parts = ["\n=== Search Results ==="]
    for i, result in enumerate(results, 1):
        content = result['content']
        if len(content) > 250:
            content = content[:247] + "..."
            
        debug_parts.extend([
            f"\nResult #{i}",
            "=" * 80,
            f"ID: {result['id']}",
            f"Source File: {result['source_file']}",
            f"Source Pages: {result['source_pages']}",
            "\n<Start Content>",
            "-" * 80,
            content,
            "-" * 80,
            "<End Content>"
        ])
    print("\n".join(debug_parts))
    
    return formatted_output

@traceable(run_type="retriever", name="run_search")
def run_search(search_query: str, processed_ids: Set[str], category_filter: str | None = None) -> List[SearchResult]:
    """
    Perform a search using Azure Cognitive Search with both semantic and vector queries.
    
    Args:
        search_query (str): The search query to use
        processed_ids (Set[str]): Set of already processed document IDs to exclude
        category_filter (str | None): Optional OData filter for category filtering
        
    Returns:
        List[SearchResult]: List of search results
    """
    # Generate vector embedding for the query
    query_vector = embeddings_model.embed_query(search_query)
    
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=K_NEAREST_NEIGHBORS,
        fields="content_vector"
    )
    
    # Create filter combining processed_ids and category filter
    filter_parts = []
    
    if processed_ids:
        ids_string = ','.join(processed_ids)
        filter_parts.append(f"not search.in(id, '{ids_string}')")
    
    if category_filter:
        filter_parts.append(f"({category_filter})")
    
    # Combine filters with 'and' if both exist
    filter_str = None
    if filter_parts:
        filter_str = " and ".join(filter_parts)

    print(f"Full Filter string: {filter_str}")
    
    # Perform the search
    results = search_client.search(
        search_text=search_query,
        vector_queries=[vector_query],
        filter=filter_str,
        select=["id", "content", "source_file", "source_pages"],
        top=NUM_SEARCH_RESULTS
    )
    
    # Convert results to SearchResult type
    search_results = []
    for result in results:
        search_result = SearchResult(
            id=result["id"],
            content=result["content"],
            source_file=result["source_file"],
            source_pages=result["source_pages"],
            score=result["@search.score"]
        )
        search_results.append(search_result)
    
    return search_results

def generate_search_query(state: ChatState) -> ChatState:
    """
    Generate an optimized search query based on the current state.
    Increments the attempt counter on each search.
    """
    # Increment attempts counter (will be 1 on first attempt)
    state["attempts"] += 1
    print(f"\nAttempt {state['attempts']} of {MAX_ATTEMPTS}")
    
    # Import the query prompt from search_prompt.py
    from search_prompt import query_prompt
    
    # Format search history and reviews together
    search_history_formatted = ""
    if state["search_history"]:
        search_history_formatted = "\n###Search History###\n"
        for i, (search, review) in enumerate(zip(state["search_history"], state["reviews"]), 1):
            search_history_formatted += f"<Attempt {i}>\n"
            search_history_formatted += f"   search_query: {search['query']}\n"
            search_history_formatted += f"   filter: {search['filter']}\n"
            search_history_formatted += f"   review: {review}\n"
    
    llm_input = f"""User Question: {state['user_input']}

{search_history_formatted}"""

    messages = [
        {"role": "system", "content": query_prompt},
        {"role": "user", "content": llm_input}
    ]
    
    # Use structured output for the search query and filter
    llm_with_search_prompt = llm.with_structured_output(SearchPromptResponse)
    search_response = llm_with_search_prompt.invoke(messages)

    # Check the search response
    print(f"search_query: {search_response.search_query}")
    print(f"filter: {search_response.filter}")
    
    # Store the search query and filter in history
    state["search_history"].append({
        "query": search_response.search_query,
        "filter": search_response.filter
    })
    
    # Run the search with both query and filter
    current_results = run_search(
        search_query=search_response.search_query,
        processed_ids=state["processed_ids"],
        category_filter=search_response.filter
    )
    
    state["current_results"] = current_results
    return state

def review_results(state: ChatState) -> ChatState:
    """
    Review current results and categorize them as valid or invalid.
    """
    review_prompt = """Review these search results and determine which contain relevant information to answering the user's question.

    Your input will contain the following information:
    
    1. User Question: The question the user asked
    2. Current Search Results: The results of the current search
    3. Previously Vetted Results: The results we've already vetted
    4. Previous Attempts: The previous search queries and filters

    Respond with:
    1. thought_process: Your analysis of the results. What is relevant and what is not? Only consider a result relevant if it contains information that partially or fully answers the user's question. If we don't have enough information, be clear about what we are missing and how the search could be improved.
    2. valid_results: List of indices (0-N) for useful results
    3. invalid_results: List of indices (0-N) for irrelevant results
    4. decision: Either "retry" if we need more info or "finalize" if we can answer the question
    """
    
    # Format the current results
    current_results_formatted = format_search_results(state["current_results"]) if state["current_results"] else "No current results."
    
    # Format the vetted results
    vetted_results_formatted = format_search_results(state["vetted_results"]) if state["vetted_results"] else "No previously vetted results."
    
    # Format search history and reviews together
    search_history_formatted = ""
    if state["search_history"]:
        search_history_formatted = "\n###Search History###\n"
        for i, (search, review) in enumerate(zip(state["search_history"], state["reviews"]), 1):
            search_history_formatted += f"<Attempt {i}>\n"
            search_history_formatted += f"   search_query: {search['query']}\n"
            search_history_formatted += f"   filter: {search['filter']}\n"
            search_history_formatted += f"   review: {review}\n"
    
    llm_input = """
    User Question: {question}
    
    Current Search Results:
    {current_results}
    
    Previously Vetted Results:
    {vetted_results}
    
    Previous Attempts:
    {search_history}
    """
    
    messages = [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": llm_input.format(
            question=state["user_input"],
            current_results=current_results_formatted,
            vetted_results=vetted_results_formatted,
            search_history=search_history_formatted
        )}
    ]
    
    review = review_llm.invoke(messages)
    print(f"### Attempt {state['attempts']} Review ###")
    print(f"\nReview thought process: {review.thought_process}")
    print(f"Valid Results: {review.valid_results}")
    print(f"Invalid Results: {review.invalid_results}")
    print(f"Decision: {review.decision}")
    
    # Update state based on review
    state["reviews"].append(review.thought_process)
    state["decisions"].append(review.decision)
    
    # Add valid results to vetted_results
    for idx in review.valid_results:
        result = state["current_results"][idx]
        state["vetted_results"].append(result)
        state["processed_ids"].add(result["id"])
    
    # Add invalid results to discarded_results
    for idx in review.invalid_results:
        result = state["current_results"][idx]
        state["discarded_results"].append(result)
        state["processed_ids"].add(result["id"])
    
    # Clear current results
    state["current_results"] = []
    
    return state

def review_router(state: ChatState) -> str:
    """Route to either retry search or go to finalize node."""
    
    # First check attempts to avoid unnecessary processing
    if state["attempts"] >= MAX_ATTEMPTS:
        print(f"\nReached maximum attempts ({MAX_ATTEMPTS}). Proceeding to finalize with current results.")
        return "finalize"
    
    # Check the last decision directly
    latest_decision = state["decisions"][-1]
    if latest_decision == "finalize":
        return "finalize"
    
    return "retry"

def finalize(state: ChatState) -> ChatState:
    """Generate final answer from vetted results."""
    # Add a note about hitting max attempts if applicable
    max_attempts_note = ""
    if state["attempts"] >= MAX_ATTEMPTS and not any("decision: finalize" in review.lower() for review in state["reviews"]):
        max_attempts_note = "\n\nNote: This answer was generated after reaching the maximum number of search attempts. It may be incomplete based on available information."
    
    final_prompt = """Create a comprehensive answer to the user's question using these vetted results.

    User Question: {question}

    Vetted Results:
    {vetted_results}

    Synthesize these results into a clear, complete answer. If there were no vetted results, say you couldn't find any relevant information to answer the question."""
    
    messages = [
        {"role": "system", "content": final_prompt},
        {"role": "user", "content": final_prompt.format(
            question=state["user_input"],
            vetted_results="\n".join([
                f"- {r['content']}" for r in state["vetted_results"]
            ])
        )}
    ]
    
    state["final_answer"] = llm.invoke(messages).content + max_attempts_note
    return state

def build_graph() -> StateGraph:
    """Build the workflow graph."""
    builder = StateGraph(ChatState)
    
    # Add nodes
    builder.add_node("generate_search_query", generate_search_query)
    builder.add_node("review_results", review_results)
    builder.add_node("finalize", finalize)
    
    # Define the flow
    builder.add_edge(START, "generate_search_query")
    builder.add_edge("generate_search_query", "review_results")
    
    # Add conditional edges from review
    builder.add_conditional_edges(
        "review_results",
        review_router,
        {
            "retry": "generate_search_query",
            "finalize": "finalize"
        }
    )
    
    # Final node goes to END
    builder.add_edge("finalize", END)
    
    return builder.compile()

if __name__ == "__main__":
    # Initialize graph
    graph = build_graph()
    
    while True:
        print("\n" + "="*50)
        user_input = input("Enter your question (or 'quit' to exit): ").strip()
        
        if user_input.lower() == 'quit':
            print("Exiting system...")
            break
        
        if not user_input:
            print("Please enter a valid question.")
            continue
        
        # Initialize state with attempts counter at 0
        initial_state = ChatState(
            user_input=user_input,
            current_results=[],
            vetted_results=[],
            discarded_results=[],
            processed_ids=set(),
            reviews=[],
            decisions=[],
            final_answer=None,
            attempts=0,
            search_history=[]
        )
        
        # Process query
        final_state = graph.invoke(initial_state)
        
        if final_state["final_answer"]:
            print("\n=== Final Answer ===")
            print(final_state["final_answer"])
        else:
            print("\nUnable to find a satisfactory answer after maximum attempts.")