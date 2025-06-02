import gradio as gr
import requests
import os

from typing import Optional
from fastapi import Request, HTTPException, status

API_URL = os.getenv("API_URL", "http://0.0.0.0:8200")


def search_and_retrieve(query, model):
    # Call the /search endpoint
    search_response = requests.post(
        f"{API_URL}/api/search", json={"query": query, "model": model}
    )
    search_result = search_response.json()

    # Call the /retrieve endpoint
    retrieve_response = requests.post(
        f"{API_URL}/api/retrieve", json={"query": query, "model": model}
    )
    retrieve_result = retrieve_response.json()

    return (
        search_result["answer"],
        retrieve_result["milvus_retrieved_doc"],
        retrieve_result["bm25_retrieved_doc"],
        retrieve_result["reranked"],
    )


def get_available_models():
    response = requests.get(f"{API_URL}/api/list_available_models")
    return response.json()["models"]


def create_document_navigator(name):
    with gr.Column():
        gr.Markdown(f"### {name} Retrieved Documents")
        doc_text = gr.Textbox(label="Document", interactive=False, lines=10)
        with gr.Row():
            prev_button = gr.Button("Previous")
            doc_number = gr.Number(value=1, label="Document Number", interactive=False)
            next_button = gr.Button("Next")
    return doc_text, prev_button, doc_number, next_button


def update_document(docs, direction, current):
    current += direction
    if current < 1:
        current = len(docs)
    elif current > len(docs):
        current = 1
    return docs[current - 1], current


with gr.Blocks() as demo:
    gr.Markdown("# RAG Search Demo")

    with gr.Row():
        with gr.Column(scale=1):
            query_input = gr.Textbox(
                label="Search Query", placeholder="Enter your search query here..."
            )
            model_dropdown = gr.Dropdown(
                label="Select Model",
                choices=get_available_models(),
                value=get_available_models()[0],
            )
            search_button = gr.Button("Search")

        with gr.Column(scale=1):
            llm_answer = gr.Textbox(label="LLM Answer", interactive=False)

    milvus_doc, milvus_prev, milvus_num, milvus_next = create_document_navigator(
        "Milvus"
    )
    bm25_doc, bm25_prev, bm25_num, bm25_next = create_document_navigator(
        "OpenSearch (BM25)"
    )
    reranked_doc, reranked_prev, reranked_num, reranked_next = (
        create_document_navigator("Reranked")
    )

    milvus_docs = gr.State([])
    bm25_docs = gr.State([])
    reranked_docs = gr.State([])

    search_button.click(
        search_and_retrieve,
        inputs=[query_input, model_dropdown],
        outputs=[llm_answer, milvus_docs, bm25_docs, reranked_docs],
    ).then(
        lambda docs: (docs[0] if docs else "", 1),
        inputs=[milvus_docs],
        outputs=[milvus_doc, milvus_num],
    ).then(
        lambda docs: (docs[0] if docs else "", 1),
        inputs=[bm25_docs],
        outputs=[bm25_doc, bm25_num],
    ).then(
        lambda docs: (docs[0] if docs else "", 1),
        inputs=[reranked_docs],
        outputs=[reranked_doc, reranked_num],
    )

    for docs, doc, prev, num, next in [
        (milvus_docs, milvus_doc, milvus_prev, milvus_num, milvus_next),
        (bm25_docs, bm25_doc, bm25_prev, bm25_num, bm25_next),
        (reranked_docs, reranked_doc, reranked_prev, reranked_num, reranked_next),
    ]:
        prev.click(
            update_document,
            inputs=[docs, gr.Number(value=-1, visible=False), num],
            outputs=[doc, num],
        )
        next.click(
            update_document,
            inputs=[docs, gr.Number(value=1, visible=False), num],
            outputs=[doc, num],
        )

demo.launch(
    server_name="0.0.0.0",
    server_port=10200,
    debug=True,
    max_threads=2,
    auth=("admin", "pass1234"),
)
