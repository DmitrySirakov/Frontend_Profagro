import os
import json
import requests
import logging
import gradio as gr

logging.basicConfig(level=logging.INFO)
API_URL = os.getenv("API_URL", "http://0.0.0.0:8200")


def convert_gradio_history_to_api_format(gradio_history):
    """
    Преобразует историю из формата Gradio (списки пар сообщений)
    в формат, ожидаемый API (списки словарей с 'role' и 'content').
    """
    api_history = []
    for pair in gradio_history:
        if len(pair) != 2:
            continue
        user_msg, assistant_msg = pair
        api_history.append({"role": "user", "content": user_msg})
        api_history.append({"role": "assistant", "content": assistant_msg})
    return api_history


def chat_with_llm_streaming(message, history):
    """
    Функция для общения с LLM с поддержкой стриминга, обрабатывает как текстовые данные,
    так и поток ссылок (metadata) с бекенда.
    """
    if history is None:
        history = []

    api_history = convert_gradio_history_to_api_format(history)
    api_history.append({"role": "user", "content": message})
    logging.info(f"Отправляем историю: {api_history}")

    response = requests.post(
        f"{API_URL}/api/agent",
        json={"chat_history": api_history},
        stream=True,
        timeout=120,  # Таймаут для запросов
    )

    response.raise_for_status()

    assistant_response = ""
    event_type = None
    buffer = ""

    # Обработка Server-Sent Events (SSE)
    for line in response.iter_lines(decode_unicode=True):
        if not line.strip():
            # Конец блока события: обрабатываем накопленные данные
            if event_type and buffer:
                try:
                    data = json.loads(buffer)
                except json.JSONDecodeError:
                    logging.warning(f"Некорректный JSON: {buffer}")
                    event_type = None
                    buffer = ""
                    continue

                if event_type == "data":
                    content = data.get("content", "")
                    assistant_response += content
                    yield assistant_response

                elif event_type == "done":
                    break

            # Сброс переменных для следующего события
            event_type = None
            buffer = ""
            continue

        # Обработка строки события
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            buffer += line[6:]

    logging.info(f"Стрим завершен: {assistant_response}")
    history.append({"role": "assistant", "content": assistant_response})


if __name__ == "__main__":
    gr.ChatInterface(
        chat_with_llm_streaming,
        chatbot=gr.Chatbot(height=500),
        textbox=gr.Textbox(
            placeholder="Введите сообщение и нажмите Enter", container=False, scale=7
        ),
        title="Чат-бот Профагро",
        description="Задай вопрос по технике AMAZONE",
        theme="soft",
        cache_examples=True,
        retry_btn="Повторить диалог полностью",
        undo_btn="Удалить предыдущее сообщение",
        clear_btn="Очистить историю чата",
    ).launch(
        server_name="0.0.0.0",
        server_port=10300,
        debug=True,
        auth=("admin", "pass1234"),
    )
