import os
import json
import logging
import asyncio
import aiohttp
import boto3
import tempfile
import time
import urllib.parse
import re
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import (
    InputMediaPhoto,
    InputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_URL = os.getenv("API_URL", "http://0.0.0.0:8200")
BOT_TOKEN = os.getenv("BOT_TOKEN")

S3_BUCKET = os.getenv("INDEXER_S3_BUCKET", "profagro-docs")
S3_ACCESS_KEY = os.getenv("INDEXER_S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("INDEXER_S3_SECRET_KEY")
S3_ENDPOINT = os.getenv("INDEXER_S3_ENDPOINT")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

s3_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    endpoint_url=S3_ENDPOINT,
    region_name="ru-central-1",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Храним историю диалогов
conversations = {}

# Создаём кнопочную клавиатуру
start_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
start_keyboard.add(KeyboardButton("Начать новый диалог"))
start_keyboard.add(KeyboardButton("Инструкция"))

company_keyboard = InlineKeyboardMarkup(row_width=2)
company_keyboard.add(
    InlineKeyboardButton("Amazone", callback_data="company_amazone"),
    InlineKeyboardButton("Kverneland", callback_data="company_kverneland"),
)

model_keyboard = InlineKeyboardMarkup(row_width=2)
model_keyboard.add(
    InlineKeyboardButton("OpenAI GPT-4o", callback_data="model_GPT4o"),
    InlineKeyboardButton("СБЕР GigaChat-MAX", callback_data="model_GigaChat-MAX"),
)


def normalize_key(key: str) -> str:
    return urllib.parse.quote(key, safe="/")


async def download_image_from_s3(s3_key: str) -> str:
    loop = asyncio.get_event_loop()
    local_fd, local_path = tempfile.mkstemp()
    os.close(local_fd)

    logger.info(f"Using raw key: {s3_key}")

    def download():
        try:
            s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
            s3_client.download_file(S3_BUCKET, s3_key, local_path)
            return local_path
        except Exception as e:
            logger.error(f"Ошибка скачивания {s3_key}: {e}")
            return None

    local_file = await loop.run_in_executor(None, download)
    return local_file


def simple_markdown_to_html(md_text: str) -> str:
    """
    Упрощённое преобразование Markdown-разметки в HTML.
    Telegram не поддерживает <br> в parse_mode=HTML, поэтому заменяем на \n.
    """
    # Заменяем заголовки на <b>…</b> + перенос строки
    md_text = re.sub(r"(?m)^#{3}\s+(.*?)$", r"<b>\1</b>\n", md_text)
    md_text = re.sub(r"(?m)^#{2}\s+(.*?)$", r"<b>\1</b>\n", md_text)
    md_text = re.sub(r"(?m)^#\s+(.*?)$", r"<b>\1</b>\n", md_text)

    # Жирный текст
    md_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", md_text, flags=re.DOTALL)

    # Курсив
    md_text = re.sub(r"_(.*?)_", r"<i>\1</i>", md_text, flags=re.DOTALL)

    return md_text


def format_date_yyyymmdd(date_str: str) -> str:
    """
    Преобразует дату из формата YYYYMMDD (например, 20210127)
    в формат DD.MM.YYYY (например, 27.01.2021).
    """
    if len(date_str) == 8 and date_str.isdigit():
        year = date_str[0:4]
        month = date_str[4:6]
        day = date_str[6:8]
        return f"{day}.{month}.{year}"
    return date_str  # fallback, если формат не совпал


def format_duration_secs(secs: int) -> str:
    """
    Преобразует количество секунд в строку вида Xч Yмин Zсек.
    Пример: 4125 -> '1ч 8мин 45сек'.
    """
    hours = secs // 3600
    remainder = secs % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    return f"{hours}ч {minutes}мин {seconds}сек"


@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    conversations[message.chat.id] = []
    await message.answer(
        "Добро пожаловать! Выберите нужный пункт меню:", reply_markup=start_keyboard
    )


@dp.message_handler(lambda message: message.text == "Начать новый диалог")
async def new_dialog_handler(message: types.Message):
    conversations[message.chat.id] = {"history": [], "company": None}

    await message.answer(
        "Новый диалог начат. Выберите пожалуйста компанию, по чьей технической документации вы хотите поговорить:",
        reply_markup=company_keyboard,  # Inline клавиатура для выбора компании
    )


@dp.callback_query_handler(lambda c: c.data.startswith("company_"))
async def handle_company_choice(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    company = callback_query.data.split("_")[
        1
    ]  # Получаем выбор компании (amazone или kverneland)

    conversations[chat_id]["company"] = company.lower()
    conversations[chat_id]["history"].append(
        {"role": "system", "content": f"Компания: {company}"}
    )

    # Отправляем сообщение с предложением выбрать модель
    await bot.edit_message_text(
        f"Вы выбрали компанию {company.upper()}. Теперь выберите модель для общения:",
        chat_id,
        callback_query.message.message_id,
        reply_markup=model_keyboard,  # Inline клавиатура для выбора модели
    )

    # Удаляем callback_query после обработки
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("model_"))
async def handle_model_choice(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    model = callback_query.data.split("_")[1]  # Получаем модель (gpt4o или gigachat)

    # Сохраняем выбранную модель в историю
    conversations[chat_id]["model"] = model

    await bot.edit_message_text(
        f"Вы выбрали модель {model} и техническую документацию компании {conversations[chat_id]['company'].upper()}. Можете писать ваш запрос.",
        chat_id,
        callback_query.message.message_id,
        reply_markup=None,  # Убираем inline-кнопки
    )

    # Удаляем callback_query после обработки
    await callback_query.answer()


@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_message(message: types.Message):
    chat_id = message.chat.id
    user_text = message.text

    if chat_id not in conversations:
        conversations[chat_id] = {"history": [], "company": None, "model": None}

    history = conversations[chat_id]["history"]
    company = conversations[chat_id]["company"]
    model = conversations[chat_id]["model"]

    # Проверяем, была ли выбрана компания
    if not company:
        await message.answer("Компания не выбрана, пожалуйста, выберите компанию.")
        return

    if not model:
        await message.answer("Модель не выбрана, пожалуйста, выберите модель.")
        return

    history.append({"role": "user", "content": user_text})

    bot_message = await message.answer("⏳ Обработка вашего запроса...")
    bot_message_id = bot_message.message_id

    assistant_response = ""

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "chat_history": history,
                "company": company,  # Добавляем компанию в запрос
            }
            if model == "GPT4o":
                api_url = f"{API_URL}/api/agent"
            elif model == "GigaChat-MAX":
                api_url = f"{API_URL}/api/agent_gigachat"
            else:
                await bot.edit_message_text(
                    "Ошибка: неверно выбрана модель.",
                    chat_id,
                    bot_message_id,
                    parse_mode="HTML",
                )
                return
            async with session.post(api_url, json=payload, timeout=300) as resp:
                if resp.status != 200:
                    await bot.edit_message_text(
                        "Ошибка при обращении к API.",
                        chat_id,
                        bot_message_id,
                        parse_mode="HTML",
                    )
                    return

                event_type = None
                buffer = ""
                last_edit_time = time.time()

                while not resp.content.at_eof():
                    raw_line = await resp.content.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8").rstrip("\n")

                    # Обработка блочного разделителя SSE
                    if line.strip() == "":
                        if event_type and buffer:
                            try:
                                data = json.loads(buffer)
                            except json.JSONDecodeError:
                                logger.warning(f"Некорректный JSON: {buffer}")
                                event_type = None
                                buffer = ""
                                continue

                            if event_type == "data":
                                content = data.get("content", "")
                                assistant_response += content

                                # Периодически подправляем отображение
                                if time.time() - last_edit_time > 1.0:
                                    html_preview = simple_markdown_to_html(
                                        assistant_response
                                    )
                                    await bot.edit_message_text(
                                        html_preview,
                                        chat_id,
                                        bot_message_id,
                                        parse_mode="HTML",
                                    )
                                    last_edit_time = time.time()

                            elif event_type == "metadata":
                                image_list = []
                                doc_sources = {}
                                youtube_refs = []

                                for meta in data.get("tool_messages", []):
                                    logger.info(f"Глобальная проверка: {meta}")
                                    source = meta.get("source", "")
                                    image_info = meta.get("image", "")
                                    video_name = meta.get("video_name", "")
                                    video_date = meta.get("video_date", "")
                                    video_len = meta.get("video_len", "")

                                    # Список картинок, которые будем скачивать
                                    if image_info:
                                        image_list.append(image_info)

                                    # Определяем, что это за источник
                                    if "youtube" in source:
                                        # Добавляем в youtube_refs, если хотя бы есть название
                                        # или сама ссылка. Можно расширить при необходимости.
                                        if video_name:
                                            ref_str = f"«{video_name}»"
                                            # Преобразуем дату
                                            if video_date:
                                                ref_str += f", дата: {format_date_yyyymmdd(video_date)}"
                                            # Преобразуем длительность
                                            if video_len.isdigit():
                                                duration_str = format_duration_secs(
                                                    int(video_len)
                                                )
                                                ref_str += (
                                                    f", длительность: {duration_str}"
                                                )
                                            youtube_refs.append(ref_str)

                                    elif source == "document":
                                        # Если пришли отдельные метаданные для документа.
                                        # Или используем поведение "иначе" (depends on your agent logic)
                                        pass

                                    else:
                                        # Предполагаем, что это документ, если есть image_info
                                        if image_info:
                                            parts = image_info.split("/")
                                            if len(parts) >= 2:
                                                doc_name = parts[-2].strip()
                                                page_part = parts[-1].strip()
                                                page_number = (
                                                    page_part.replace("page_", "")
                                                    .replace(".png", "")
                                                    .strip()
                                                )
                                                # Пропускаем пустые названия или страницы
                                                if doc_name and page_number:
                                                    if doc_name not in doc_sources:
                                                        doc_sources[doc_name] = set()
                                                    doc_sources[doc_name].add(
                                                        page_number
                                                    )

                                # Скачиваем и отправляем картинки (если есть)
                                media_files = []
                                local_files = []
                                for image_key in image_list:
                                    local_file = await download_image_from_s3(image_key)
                                    if local_file:
                                        local_files.append(local_file)
                                        media_files.append(
                                            InputMediaPhoto(InputFile(local_file))
                                        )

                                if media_files:
                                    await bot.send_media_group(chat_id, media_files)

                                # Удаляем временные файлы
                                for local_path in local_files:
                                    try:
                                        os.remove(local_path)
                                    except Exception as e:
                                        logger.warning(
                                            f"Не удалось удалить файл {local_path}: {e}"
                                        )

                                # Проверяем, действительно ли есть источники
                                has_docs = bool(doc_sources)
                                has_videos = bool(youtube_refs)

                                # Если ни документации, ни YouTube-ссылок нет — пропускаем отправку
                                if has_docs or has_videos:
                                    ref_text_lines = []
                                    ref_text_lines.append(
                                        "<b>Информация взята из:</b>\n"
                                    )

                                    # Документация
                                    if has_docs:
                                        ref_text_lines.append("<b>- Документация</b>")
                                        for doc_name, pages_set in doc_sources.items():
                                            # Если всё же что-то не распарсилось, doc_name может быть пустым
                                            if not doc_name:
                                                continue
                                            # Сортируем страницы (если это цифры, иначе строка)
                                            sorted_pages = sorted(
                                                pages_set,
                                                key=lambda p: (
                                                    int(p) if p.isdigit() else p
                                                ),
                                            )
                                            pages_str = ", ".join(sorted_pages)
                                            ref_text_lines.append(
                                                f"-> «{doc_name}», стр. {pages_str}"
                                            )
                                        ref_text_lines.append("")

                                    # YouTube
                                    if has_videos:
                                        ref_text_lines.append("<b>- YouTube</b>")
                                        for ref in youtube_refs:
                                            ref_text_lines.append(f"-> {ref}")
                                        ref_text_lines.append("")

                                    final_ref_text = "\n".join(ref_text_lines).strip()
                                    # Убедимся, что финальный текст не пуст (если, допустим,
                                    # doc_name оказался пустым и ничего не вышло)
                                    # Если что-то осталось — отправляем
                                    if (
                                        final_ref_text
                                        and final_ref_text
                                        != "<b>Информация взята из:</b>"
                                    ):
                                        await bot.send_message(
                                            chat_id, final_ref_text, parse_mode="HTML"
                                        )

                            elif event_type == "done":
                                break

                        event_type = None
                        buffer = ""
                        continue

                    # Стандартная обработка SSE-заголовков
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        buffer += line[6:]
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {e}")
        await bot.edit_message_text(
            "Произошла ошибка при обработке запроса.",
            chat_id,
            bot_message_id,
            parse_mode="HTML",
        )
        return

    if assistant_response.strip():
        html_final = simple_markdown_to_html(assistant_response)
        await bot.edit_message_text(
            html_final, chat_id, bot_message_id, parse_mode="HTML"
        )
    else:
        await bot.edit_message_text(
            "Пустой ответ от ассистента.", chat_id, bot_message_id, parse_mode="HTML"
        )

    history.append({"role": "assistant", "content": assistant_response})


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
