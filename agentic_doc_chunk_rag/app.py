# app.py
import json
import threading
import queue
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from agentic_doc_chunk_rag_v2 import graph_invoke, ChatState

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:3001"])

def stream_chat_response(user_input: str):
    """Generator that runs the agent graph in a background thread and yields SSE events."""
    event_queue = queue.Queue()

    # Initialize state without an emit callback.
    initial_state: ChatState = {
        "user_input": user_input,
        "current_results": [],
        "vetted_results": [],
        "discarded_results": [],
        "processed_ids": set(),
        "reviews": [],
        "decisions": [],
        "final_answer": None,
        "attempts": 0,
        "search_history": [],
        "thought_process": []
    }

    # Run the graph in a background thread.
    def run_graph():
        try:
            for event in graph_invoke(initial_state):
                event_queue.put(event)
        except Exception as e:
            event_queue.put({"event_type": "server-error", "message": str(e)})
        # Always signal completion.
        event_queue.put({"event_type": "end"})

    threading.Thread(target=run_graph).start()

    # Yield SSE events from the queue.
    while True:
        event = event_queue.get()  # Blocking call.
        sse_message = f"event: {event['event_type']}\n" \
                      f"data: {json.dumps(event)}\n\n"
        yield sse_message
        if event.get("event_type") == "end":
            break

@app.route("/chat", methods=["GET", "POST"])
def chat():
    try:
        if request.method == "POST":
            data = request.get_json()
            if not data or "user_input" not in data:
                return jsonify({"error": "Missing 'user_input' in request payload."}), 400
            user_input = data["user_input"].strip()
        else:
            user_input = request.args.get("user_input", "").strip()
            if not user_input:
                return jsonify({"error": "Missing 'user_input' query parameter."}), 400

        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
        return Response(stream_chat_response(user_input), headers=headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
