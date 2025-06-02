# Frontend_Profagro

## 🛠️ Стек frontend

![Python](https://img.shields.io/badge/-Python_3.10+-090909?style=for-the-badge&logo=python)
![Gradio](https://img.shields.io/badge/-Gradio-090909?style=for-the-badge&logo=gradio)
![Aiogram](https://img.shields.io/badge/-Aiogram-090909?style=for-the-badge&logo=telegram)
![OpenAI](https://img.shields.io/badge/-OpenAI-090909?style=for-the-badge&logo=openai)
![Docker](https://img.shields.io/badge/-Docker-090909?style=for-the-badge&logo=docker)

[Документация проекта на DeepWiki](https://deepwiki.com/DmitrySirakov/Frontend_Profagro)

## Описание

Frontend реализует пользовательские интерфейсы для взаимодействия механизатора и инженера с LLM-ассистентом. Включает web-приложения на Gradio и Telegram-бота, обеспечивающих мгновенный доступ к инструкциям, фото-схемам и видеогайдам в полевых условиях.

## Архитектура и сценарии использования

- **chat-agent-gradio/** — web-интерфейс для диалога с LLM-ассистентом, получения персонализированных инструкций и ссылок на источники.
- **search-gradio/** — web-интерфейс для гибридного поиска по базе знаний (PDF, видео, схемы).
- **telegram-bot/** — Telegram-бот для мобильного доступа к ассистенту, интеграция с фото и видео, поддержка быстрого поиска и получения инструкций прямо в поле.

## Технологический стек

- Python 3.10+
- Gradio
- aiogram (Telegram Bot)
- openai
- Docker

## Структура

- `chat-agent-gradio/` — Gradio-интерфейс для чата
- `search-gradio/` — Gradio-интерфейс для поиска
- `telegram-bot/` — Telegram-бот

## Запуск

### Через Docker Compose (рекомендуется)
1. Перейдите в корень репозитория
2. Запустите:
   ```bash
   docker-compose up --build
   ```

### Локально (пример для chat-agent-gradio)
1. Установите зависимости:
   ```bash
   cd frontend/chat-agent-gradio
   pip install -r requirements.txt
   ```
2. Запустите Gradio-приложение:
   ```bash
   python project/app.py
   ```

### Локально (пример для telegram-bot)
1. Установите зависимости:
   ```bash
   cd frontend/telegram-bot
   pip install -r requirements.txt
   ```
2. Запустите бота:
   ```bash
   python project/app.py
   ```

## Практическая значимость
- Интерфейсы протестированы в ООО «ПрофАгро» в реальных производственных условиях.
- Telegram-бот позволяет механизатору получать инструкции и схемы без отрыва от работы.
- Web-интерфейсы подходят для инженеров и агрономов.
