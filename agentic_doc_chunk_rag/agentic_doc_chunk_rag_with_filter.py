from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from pydantic import BaseModel
from typing import List, Dict, Any, Union, Literal, get_args
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

# Create a type for indices from 0 to NUM_SEARCH_RESULTS-1
SearchResultIndex = Literal[tuple(range(NUM_SEARCH_RESULTS))]

# Type Definitions
class SearchResult(TypedDict):
    id: str
    content: str
    source_file: str
    source_pages: int
    score: float

class ReviewDecision(BaseModel):
    """Schema for review agent decisions"""
    thought_process: str
    valid_results: List[SearchResultIndex]  # Indices of valid results
    invalid_results: List[SearchResultIndex]  # Indices of invalid results
    decision: Literal["retry", "finalize"]

class SearchPromptResponse(BaseModel):
    """Schema for search prompt responses"""
    search_query: str
    filter: str | None

# Extend ChatState to include a list of thought process steps.
class ChatState(TypedDict):
    user_input: str
    current_results: List[SearchResult]
    vetted_results: List[SearchResult]
    discarded_results: List[SearchResult]
    processed_ids: Set[str]  # Track all processed document IDs
    reviews: List[str]       # Thought processes from reviews
    decisions: List[str]     # Store the actual decisions
    final_answer: str | None
    attempts: int            # Track number of search attempts
    search_history: List[Dict[str, Any]]  # Track previous search queries and filters
    thought_process: List[Dict[str, Any]]  # List of thought process steps

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
    for i, result in enumerate(results, 0):
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
    formatted_output = "\n".join(output_parts)
    return formatted_output

@traceable(run_type="retriever", name="run_search")
def run_search(search_query: str, processed_ids: Set[str], category_filter: str | None = None) -> List[SearchResult]:
    """
    Perform a search using Azure Cognitive Search with both semantic and vector queries.
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
    filter_str = " and ".join(filter_parts) if filter_parts else None

    # Perform the search
    results = search_client.search(
        search_text=search_query,
        vector_queries=[vector_query],
        filter=filter_str,
        select=["id", "content", "source_file", "source_pages"],
        top=NUM_SEARCH_RESULTS
    )
    
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
    print('event_type :retrieve')
    state["attempts"] += 1
    from search_prompt import query_prompt
    
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
    
    llm_with_search_prompt = llm.with_structured_output(SearchPromptResponse)
    search_response = llm_with_search_prompt.invoke(messages)
    
    # Record this search query in history.
    state["search_history"].append({
        "query": search_response.search_query,
        "filter": search_response.filter
    })
    
    # Run the search.
    current_results = run_search(
        search_query=search_response.search_query,
        processed_ids=state["processed_ids"],
        category_filter=search_response.filter
    )
    state["current_results"] = current_results

    # Append details to the thought_process list.
    state["thought_process"].append({
        "type": "retrieve",
        "details": {
            "user_question": state["user_input"],
            "generated_search_query": search_response.search_query,
            "filter": search_response.filter,
            "results_summary": [
                {
                    "source_file": res["source_file"],
                    "source_pages": res["source_pages"]
                } for res in current_results
            ]
        }
    })
    
    return state

def review_results(state: ChatState) -> ChatState:
    """
    Review current results and categorize them as valid or invalid.
    """
    print('event_type :review')
    
    review_prompt = """Review these search results and determine which contain relevant information to answering the user's question.
    
Your input will contain the following information:
    
1. User Question: The question the user asked
2. Current Search Results: The results of the current search
3. Previously Vetted Results: The results we've already vetted
4. Previous Attempts: The previous search queries and filters

Respond with:
1. thought_process: Your analysis of the results. Is this a general or specific question? What is relevant and what is not? Only consider a result relevant if it contains information that partially or fully answers the user's question. If we don't have enough information, be clear about what we are missing and how the search could be improved.
2. valid_results: List of indices (0-N) for useful results
3. invalid_results: List of indices (0-N) for irrelevant results
4. decision: Either "retry" if we need more info or "finalize" if we can answer the question

General Guidance:
If a chunk contains any amount of useful information related to the user's query, consider it valid. Only discard chunks that will not help constructing the final answer.
DO NOT discard chunks that contain partially useful information. We are trying to construct RFP responses, so more detail is better. We are not aiming for conciseness.

For Specific Questions:
If the user asks a very specific question, such as for an example of a specific type of case study or scenario, only consider chunks that contain information that is specifically related to that question. Discard other chunks.

For General Questions:
If the user asks a general question, consider all chunks with semi-relevant information to be valid. Our goal is to compile a comprehensive answer to the user's question.
Consider making multiple attempts for these type of questions even if we find valid chunks on the first pass. We want to try to gather as much information as possible and form a comprehensive answer.
"""
    
    current_results_formatted = format_search_results(state["current_results"]) if state["current_results"] else "No current results."
    vetted_results_formatted = format_search_results(state["vetted_results"]) if state["vetted_results"] else "No previously vetted results."
    
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

<Current Search Results to review>
{current_results}
<end current search results to review>

<previously vetted results, do not review>
{vetted_results}
<end previously vetted results, do not review>

<Previous Attempts>
{search_history}
<end Previous Attempts>
""".format(
        question=state["user_input"],
        current_results=current_results_formatted,
        vetted_results=vetted_results_formatted,
        search_history=search_history_formatted
    )
    
    messages = [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": llm_input}
    ]
    
    review = review_llm.invoke(messages)
    
    # Append the review step to the thought_process list.
    state["thought_process"].append({
        "type": "review",
        "details": {
            "review_thought_process": review.thought_process,
            "decision": review.decision
        }
    })
    
    state["reviews"].append(review.thought_process)
    state["decisions"].append(review.decision)
    
    for idx in review.valid_results:
        result = state["current_results"][idx]
        state["vetted_results"].append(result)
        state["processed_ids"].add(result["id"])
    
    for idx in review.invalid_results:
        result = state["current_results"][idx]
        state["discarded_results"].append(result)
        state["processed_ids"].add(result["id"])
    
    state["current_results"] = []
    return state

def review_router(state: ChatState) -> str:
    """Route to either retry search or go to finalize node."""
    if state["attempts"] >= MAX_ATTEMPTS:
        print(f"\nReached maximum attempts ({MAX_ATTEMPTS}). Proceeding to finalize with current results.")
        return "finalize"
    
    latest_decision = state["decisions"][-1]
    if latest_decision == "finalize":
        return "finalize"
    
    return "retry"

def finalize(state: ChatState) -> ChatState:
    """Generate final answer from vetted results."""
    final_prompt = """Create a comprehensive answer to the user's question using the vetted results.
    
    Do not include any information about the search process or the vetting process in your answer.
    Do not answer outside of the context of the vetted results. 
    Do not make up information or make assumptions.
    Do not output PII. 


    Scrutinize the user's question and make sure they are not asking for anything unethical or against company policy.
    If they are, say that you cannot answer that question.

    
    """
    
    llm_input = """Create a comprehensive answer to the user's question using these vetted results.

User Question: {question}

Vetted Results:
{vetted_results}

Synthesize these results into a clear, complete answer. If there were no vetted results, say you couldn't find any relevant information to answer the question."""
    
    messages = [
        {"role": "system", "content": final_prompt},
        {"role": "user", "content": llm_input.format(
            question=state["user_input"],
            vetted_results="\n".join([f"- {r['content']}" for r in state["vetted_results"]])
        )}
    ]
    
    response_chunks = []
    for chunk in llm.stream(messages):
        response_chunks.append(chunk.content)
        print(chunk.content, end="", flush=True)
    
    final_response = "".join(response_chunks)
    state["final_answer"] = final_response
    
    # Append the final response to the thought_process list.
    state["thought_process"].append({
        "type": "response",
        "details": {
            "final_answer": final_response
        }
    })
    
    return state

def build_graph() -> StateGraph:
    """Build the workflow graph."""
    builder = StateGraph(ChatState)
    builder.add_node("generate_search_query", generate_search_query)
    builder.add_node("review_results", review_results)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "generate_search_query")
    builder.add_edge("generate_search_query", "review_results")
    builder.add_conditional_edges(
        "review_results",
        review_router,
        {
            "retry": "generate_search_query",
            "finalize": "finalize"
        }
    )
    builder.add_edge("finalize", END)
    return builder.compile()

if __name__ == "__main__":
    # Initialize graph
    graph = build_graph()
    
    while True:
        user_input = input("Enter your question (or 'quit' to exit): ").strip()
        if user_input.lower() == 'quit':
            print("Exiting system...")
            break
        
        if not user_input:
            print("Please enter a valid question.")
            continue
        
        # Initialize state with thought_process as an empty list.
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
            search_history=[],
            thought_process=[]
        )
        
        final_state = graph.invoke(initial_state)
        
        if final_state["final_answer"]:
            # Build the final payload to return via your API.
            final_payload = {
                "final_answer": final_state["final_answer"],
                "citations": final_state["vetted_results"],  # Renaming vetted_results as citations
                "thought_process": final_state["thought_process"]
            }
            
            # For demonstration purposes, we're printing the payload.
            # In your API, you'd return this payload as a JSON response.
            import json
            print("\n=== API Return Payload ===")
            print(json.dumps(final_payload, indent=4))
        else:
            print("\nUnable to find a satisfactory answer after maximum attempts.")
