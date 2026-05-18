"""
Telegram Quiz Bot — БСТ (Безопасность Сетевых Технологий)
python-telegram-bot >= 20.x

Установка:
    pip install python-telegram-bot

Запуск:
    python bot.py

Команды:
    /start   — главное меню
    /exam    — экзаменационный режим (20 случайных вопросов, как на экзамене)
    /full    — полный квиз (все 500 вопросов)
    /topic   — квиз по теме
    /score   — текущий счёт
    /stop    — остановить квиз
"""

import asyncio
import json
import random
import logging
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, PollAnswerHandler,
    CallbackQueryHandler, ContextTypes
)

TOKEN = "8883426873:AAGNw52M5bHp524pZRX5POft7ITpAEZ_5Bg"  # ← вставь токен от @BotFather

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Загрузка вопросов ──────────────────────────────────────────────────────────
with open("questions.json", encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

# Темы (по номерам вопросов)
TOPICS = {
    "📚 Вопросы 1–100":   list(range(0, 100)),
    "📚 Вопросы 101–200": list(range(100, 200)),
    "📚 Вопросы 201–300": list(range(200, 300)),
    "📚 Вопросы 301–400": list(range(300, 400)),
    "📚 Вопросы 401–500": list(range(400, 500)),
}


# ── Вспомогательные функции ────────────────────────────────────────────────────
def get_session(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "session" not in context.user_data:
        context.user_data["session"] = {}
    return context.user_data["session"]


def reset_session(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["session"] = {}


async def send_next_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(context)
    queue: list = session.get("queue", [])
    idx: int = session.get("idx", 0)

    if idx >= len(queue):
        await finish_quiz(chat_id, context)
        return

    q = queue[idx]
    total = len(queue)

    # Прогресс
    progress = f"❓ Вопрос {idx + 1}/{total}"
    if session.get("mode") == "exam":
        progress += f" | 📝 Экзамен"
    score_now = session.get("score", 0)
    if idx > 0:
        progress += f" | ✅ {score_now}/{idx}"

    # Отправляем Poll типа QUIZ
    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"{progress}\n\n{q['q']}",
        options=q["o"],
        type=Poll.QUIZ,
        correct_option_id=q["a"],
        is_anonymous=False,
        explanation=f"✅ Правильный ответ: {['A','B','C','D'][q['a']]}) {q['o'][q['a']]}",
        open_period=30,  # 30 секунд на ответ
    )

    # Сохраняем poll_id → вопрос
    session["poll_id"] = msg.poll.id
    session["chat_id"] = chat_id
    session["idx"] = idx + 1
    session["current_correct"] = q["a"]


async def finish_quiz(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(context)
    score = session.get("score", 0)
    total = session.get("idx", 0)
    mode = session.get("mode", "")

    pct = round(score / total * 100) if total > 0 else 0

    if pct >= 90:
        grade = "🏆 Отлично!"
    elif pct >= 75:
        grade = "👍 Хорошо!"
    elif pct >= 60:
        grade = "😐 Удовлетворительно"
    else:
        grade = "❌ Нужно повторить"

    text = (
        f"🎯 *Квиз завершён!*\n\n"
        f"✅ Правильных ответов: *{score}/{total}*\n"
        f"📊 Процент: *{pct}%*\n"
        f"🎖 Оценка: {grade}\n\n"
    )
    if mode == "exam":
        text += "📝 _Экзаменационный режим: 20 вопросов по 2 балла = 40 баллов max_\n"
        text += f"💯 Ваши баллы: *{score * 2}/40*\n\n"

    text += "Используй /start для нового квиза"

    await context.bot.send_message(chat_id, text, parse_mode="Markdown")
    reset_session(context)


# ── Обработчики команд ─────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_session(context)
    keyboard = [
        [InlineKeyboardButton("📝 Экзамен (20 вопросов)", callback_data="mode_exam")],
        [InlineKeyboardButton("📚 Полный квиз (500 вопросов)", callback_data="mode_full")],
        [InlineKeyboardButton("🎯 По теме", callback_data="mode_topic")],
        [InlineKeyboardButton("🔀 Случайные 50", callback_data="mode_random50")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔐 *Квиз: Безопасность Сетевых Технологий*\n\n"
        "КазНИТУ | 3 курс | 500 вопросов\n\n"
        "Выбери режим:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(context)
    if not session:
        await update.message.reply_text("Нет активного квиза. /start для начала.")
        return
    score = session.get("score", 0)
    idx = session.get("idx", 0)
    reset_session(context)
    await update.message.reply_text(
        f"⏹ Квиз остановлен.\n"
        f"Результат: {score}/{idx} правильных ответов.\n\n"
        f"/start — начать заново"
    )


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(context)
    if not session or "idx" not in session:
        await update.message.reply_text("Нет активного квиза. /start для начала.")
        return
    score = session.get("score", 0)
    idx = session.get("idx", 0)
    total = len(session.get("queue", []))
    pct = round(score / idx * 100) if idx > 0 else 0
    await update.message.reply_text(
        f"📊 Текущий счёт: {score}/{idx} ({pct}%)\n"
        f"Осталось вопросов: {total - idx}"
    )


# ── Callback-кнопки ────────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    session = get_session(context)

    if data == "mode_exam":
        session["queue"] = random.sample(ALL_QUESTIONS, 20)
        session["score"] = 0
        session["idx"] = 0
        session["mode"] = "exam"
        await query.edit_message_text(
            "📝 *Экзаменационный режим*\n"
            "20 случайных вопросов, 30 секунд на каждый.\n"
            "Начинаем! 🚀",
            parse_mode="Markdown"
        )
        await send_next_question(chat_id, context)

    elif data == "mode_full":
        q_list = ALL_QUESTIONS.copy()
        random.shuffle(q_list)
        session["queue"] = q_list
        session["score"] = 0
        session["idx"] = 0
        session["mode"] = "full"
        await query.edit_message_text(
            "📚 *Полный квиз*\n"
            "Все 500 вопросов в случайном порядке.\n"
            "Используй /stop для остановки.\n"
            "Начинаем! 🚀",
            parse_mode="Markdown"
        )
        await send_next_question(chat_id, context)

    elif data == "mode_random50":
        session["queue"] = random.sample(ALL_QUESTIONS, 50)
        session["score"] = 0
        session["idx"] = 0
        session["mode"] = "random50"
        await query.edit_message_text(
            "🔀 *50 случайных вопросов*\n"
            "Начинаем! 🚀",
            parse_mode="Markdown"
        )
        await send_next_question(chat_id, context)

    elif data == "mode_topic":
        keyboard = []
        for i, topic in enumerate(TOPICS.keys()):
            keyboard.append([InlineKeyboardButton(topic, callback_data=f"topic_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
        await query.edit_message_text(
            "🎯 Выбери тему:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("topic_"):
        topic_idx = int(data.split("_")[1])
        topic_name = list(TOPICS.keys())[topic_idx]
        indices = TOPICS[topic_name]
        topic_questions = [ALL_QUESTIONS[i] for i in indices if i < len(ALL_QUESTIONS)]
        random.shuffle(topic_questions)
        session["queue"] = topic_questions
        session["score"] = 0
        session["idx"] = 0
        session["mode"] = f"topic"
        await query.edit_message_text(
            f"🎯 *{topic_name}*\n"
            f"{len(topic_questions)} вопросов. Начинаем! 🚀",
            parse_mode="Markdown"
        )
        await send_next_question(chat_id, context)

    elif data == "back_main":
        keyboard = [
            [InlineKeyboardButton("📝 Экзамен (20 вопросов)", callback_data="mode_exam")],
            [InlineKeyboardButton("📚 Полный квиз (500 вопросов)", callback_data="mode_full")],
            [InlineKeyboardButton("🎯 По теме", callback_data="mode_topic")],
            [InlineKeyboardButton("🔀 Случайные 50", callback_data="mode_random50")],
        ]
        await query.edit_message_text(
            "🔐 *Квиз: Безопасность Сетевых Технологий*\n\nВыбери режим:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ── Обработка ответов на Poll ──────────────────────────────────────────────────
async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = answer.user.id

    # Найти сессию пользователя
    user_data = context.application.user_data.get(user_id)
    if not user_data or "session" not in user_data:
        return

    session = user_data["session"]
    if not session or session.get("poll_id") != answer.poll_id:
        return

    # Проверяем ответ
    if answer.option_ids and answer.option_ids[0] == session.get("current_correct"):
        session["score"] = session.get("score", 0) + 1

    chat_id = session.get("chat_id")
    if chat_id:
        # Небольшая пауза, чтобы пользователь увидел результат
        await asyncio.sleep(1.5)
        await send_next_question(chat_id, context)


# ── Запуск ─────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PollAnswerHandler(poll_answer_handler))

    print("✅ Бот запущен. Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
