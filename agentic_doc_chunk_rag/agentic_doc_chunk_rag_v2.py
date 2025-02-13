# agentic_doc_chunk_rag_v2.py
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from pydantic import BaseModel
from typing import List, Dict, Any, Literal, TypedDict, Set, Generator
from dotenv import load_dotenv
import os
from langgraph.graph import StateGraph, START, END  # Not used in this refactor.
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

# Define ChatState as a TypedDict.
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
    """Format search results into a nicely formatted string."""
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
    return "\n".join(output_parts)

@traceable(run_type="retriever", name="run_search")
def run_search(search_query: str, processed_ids: Set[str], category_filter: str | None = None) -> List[SearchResult]:
    """
    Perform a search using Azure Cognitive Search with both semantic and vector queries.
    """
    query_vector = embeddings_model.embed_query(search_query)
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=K_NEAREST_NEIGHBORS,
        fields="content_vector"
    )
    filter_parts = []
    if processed_ids:
        ids_string = ','.join(processed_ids)
        filter_parts.append(f"not search.in(id, '{ids_string}')")
    if category_filter:
        filter_parts.append(f"({category_filter})")
    filter_str = " and ".join(filter_parts) if filter_parts else None

    results = search_client.search(
        search_text=search_query,
        vector_queries=[vector_query],
        filter=filter_str,
        select=["id", "content", "source_file", "source_pages"],
        top=NUM_SEARCH_RESULTS
    )
    search_results = []
    for result in results:
        search_result: SearchResult = {
            "id": result["id"],
            "content": result["content"],
            "source_file": result["source_file"],
            "source_pages": result["source_pages"],
            "score": result["@search.score"]
        }
        search_results.append(search_result)
    return search_results

def generate_search_query(state: ChatState) -> Generator[Dict[str, Any], None, ChatState]:
    """
    Generate an optimized search query based on the current state.
    Yields an intermediate event and then yields the updated state.
    """
    yield {"event_type": "retrieve", "message": "Generating search query."}
    state["attempts"] += 1

    from search_prompt import query_prompt  # Assume your prompt is defined here.
    
    search_history_formatted = ""
    if state["search_history"]:
        search_history_formatted = "\n### Search History ###\n"
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
    
    # Record search query.
    state["search_history"].append({
        "query": search_response.search_query,
        "filter": search_response.filter
    })
    
    current_results = run_search(
        search_query=search_response.search_query,
        processed_ids=state["processed_ids"],
        category_filter=search_response.filter
    )
    state["current_results"] = current_results
    
    state["thought_process"].append({
        "step": "retrieve",
        "details": {
            "user_question": state["user_input"],
            "generated_search_query": search_response.search_query,
            "filter": search_response.filter,
            "results_summary": [
                {"source_file": res["source_file"], "source_pages": res["source_pages"]}
                for res in current_results
            ]
        }
    })
    yield state

def review_results(state: ChatState) -> Generator[Dict[str, Any], None, ChatState]:
    """
    Review current results and categorize them as valid or invalid.
    Yields an intermediate event and then yields the updated state.
    """
    yield {"event_type": "review", "message": "Reviewing search results."}
    
    review_prompt = """Review these search results and determine which contain relevant information to answering the user's question.
    
Your input will contain the following information:
    
1. User Question: The question the user asked
2. Current Search Results: The results of the current search
3. Previously Vetted Results: The results we've already vetted
4. Previous Attempts: The previous search queries and filters

Respond with:
1. thought_process: Your analysis of the results. Is this a general or specific question? Which chunks are relevant and which are not? Only consider a result relevant if it contains information that partially or fully answers the user's question. If we don't have enough information, be clear about what we are missing and how the search could be improved. End by saying whether we will answer or keep looking.
2. valid_results: List of indices (0-N) for useful results
3. invalid_results: List of indices (0-N) for irrelevant results
4. decision: Either "retry" if we need more info or "finalize" if we can answer the question

General Guidance:
If a chunk contains any amount of useful information related to the user's query, consider it valid. Only discard chunks that will not help constructing the final answer.
DO NOT discard chunks that contain partially useful information. We are trying to construct detailed responses, so more detail is better. We are not aiming for conciseness.

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
        search_history_formatted = "\n### Search History ###\n"
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
    
    state["thought_process"].append({
        "step": "review",
        "details": {
            "review_thought_process": review.thought_process,
            "valid_results": [
                {
                    "source_file": state["current_results"][idx]["source_file"],
                    "source_pages": state["current_results"][idx]["source_pages"]
                }
                for idx in review.valid_results
            ],
            "invalid_results": [
                {
                    "source_file": state["current_results"][idx]["source_file"],
                    "source_pages": state["current_results"][idx]["source_pages"]
                }
                for idx in review.invalid_results
            ],
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
    yield state

def finalize(state: ChatState) -> Generator[Dict[str, Any], None, ChatState]:
    """
    Generate final answer from vetted results.
    Yields response chunk events and then yields a final payload event containing the final answer, citations, and thought process.
    """
    final_prompt = """Create a comprehensive answer to the user's question using the vetted results."""
    
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
    # Stream response chunks and yield an event for each chunk.
    for chunk in llm.stream(messages):
        response_chunks.append(chunk.content)
        yield {"event_type": "response_chunk", "chunk": chunk.content}
    final_response = "".join(response_chunks)
    state["final_answer"] = final_response
    yield {"event_type": "final_response", "message": final_response}
    
    state["thought_process"].append({
        "step": "response",
        "details": {
            "final_answer": final_response
        }
    })
    
    # Assemble final payload.
    final_payload = {
        "final_answer": final_response,
        "citations": state["vetted_results"],
        "thought_process": state["thought_process"]
    }
    yield {"event_type": "final_payload", "payload": final_payload}
    
    yield state

def review_router(state: ChatState) -> str:
    """Route to either retry search or go to finalize node."""
    if state["attempts"] >= MAX_ATTEMPTS:
        yield {"event_type": "info", "message": f"Reached maximum attempts ({MAX_ATTEMPTS}). Finalizing with current results."}
        return "finalize"
    latest_decision = state["decisions"][-1] if state["decisions"] else "finalize"
    if latest_decision == "finalize":
        return "finalize"
    return "retry"

def graph_invoke(initial_state: ChatState) -> Generator[Dict[str, Any], None, ChatState]:
    """
    Master generator that chains the graph nodes.
    It loops through generate_search_query and review_results until the decision is "finalize" or attempts exceed MAX_ATTEMPTS,
    then calls finalize.
    """
    state = initial_state
    # Loop until finalization condition is met.
    while True:
        for result in generate_search_query(state):
            if isinstance(result, dict) and "event_type" in result:
                yield result
            else:
                state = result

        for result in review_results(state):
            if isinstance(result, dict) and "event_type" in result:
                yield result
            else:
                state = result

        # Check routing decision.
        decision = state["decisions"][-1] if state["decisions"] else "finalize"
        if state["attempts"] >= MAX_ATTEMPTS or decision == "finalize":
            break
        # If decision is "retry", loop again.
    for result in finalize(state):
        if isinstance(result, dict) and "event_type" in result:
            yield result
        else:
            state = result
    return state

# The original build_graph function using StateGraph is no longer used.
# Instead, use graph_invoke directly.

if __name__ == "__main__":
    # For testing via CLI.
    initial_state = ChatState(
        user_input="What is the meaning of life?",
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
    gen = graph_invoke(initial_state)
    final_state = None
    for event in gen:
        print("EVENT:", event)
        if event.get("event_type") == "end":
            break
