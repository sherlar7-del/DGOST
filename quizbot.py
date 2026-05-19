import random
import sqlite3
from datetime import datetime
from docx import Document

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =========================
# SOZLAMALAR
# =========================

TOKEN = "8712005526:AAH-5esSoHp4E5HxrUZKFljEPO7MmWsKysM"
ADMIN_ID = 5183129765

# =========================
# DATABASE
# =========================

def get_conn():

    return sqlite3.connect(
        "bot_data.db",
        check_same_thread=False
    )

def init_db():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        tests_count INTEGER DEFAULT 0,
        total_score INTEGER DEFAULT 0,
        best_score INTEGER DEFAULT 0,
        last_active TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS allowed_users(
        user_id INTEGER PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blocked_users(
        user_id INTEGER PRIMARY KEY
    )
    """)

    conn.commit()
    conn.close()

# =========================
# SAVOLLAR
# =========================

questions = []

def load_questions():

    global questions

    try:

        doc = Document("testlar.docx")

        q = {}
        opts = []

        for p in doc.paragraphs:

            text = p.text.strip()

            if not text:
                continue

            if text.startswith(("A)", "B)", "C)", "D)")):

                opts.append(text)

            elif text.startswith("ANSWER:"):

                answer = text.replace(
                    "ANSWER:",
                    ""
                ).strip()

                q["options"] = opts.copy()
                q["answer"] = answer[0]

                questions.append(q.copy())

                q = {}
                opts = []

            else:

                q["question"] = text

        print(f"✅ {len(questions)} savol yuklandi")

    except Exception as e:

        print("❌ Savol yuklash xatosi:", e)

# =========================
# USER TEKSHIRUV
# =========================

def is_admin(user_id):

    return user_id == ADMIN_ID

def is_blocked(user_id):

    if is_admin(user_id):
        return False

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT 1
    FROM blocked_users
    WHERE user_id=?
    """, (user_id,))

    result = cur.fetchone()

    conn.close()

    return result is not None

def is_allowed(user_id):

    if is_admin(user_id):
        return True

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT 1
    FROM allowed_users
    WHERE user_id=?
    """, (user_id,))

    result = cur.fetchone()

    conn.close()

    return result is not None

# =========================
# STATISTIKA
# =========================

def update_stats(user, score):

    conn = get_conn()
    cur = conn.cursor()

    now = datetime.now().strftime(
        "%d.%m.%Y %H:%M"
    )

    cur.execute("""
    INSERT OR IGNORE INTO users(
        user_id,
        full_name,
        username
    )
    VALUES (?, ?, ?)
    """, (
        user.id,
        user.full_name,
        user.username
    ))

    cur.execute("""
    UPDATE users
    SET
        tests_count = tests_count + 1,
        total_score = total_score + ?,
        best_score = CASE
            WHEN ? > best_score
            THEN ?
            ELSE best_score
        END,
        last_active = ?
    WHERE user_id = ?
    """, (
        score,
        score,
        score,
        now,
        user.id
    ))

    conn.commit()
    conn.close()

# =========================
# PROFESSIONAL RANDOM
# =========================

def generate_quiz(user_data):

    total_questions = len(questions)

    history = user_data.get(
        "history",
        []
    )

    # Oxirgi 90 ta savol qaytmaydi
    recent_limit = 90

    recent_history = set(
        history[-recent_limit:]
    )

    available_indexes = [

        i for i in range(total_questions)

        if i not in recent_history
    ]

    # Agar kamayib qolsa reset
    if len(available_indexes) < 30:

        history = []

        available_indexes = list(
            range(total_questions)
        )

    # Kuchli random
    random.shuffle(available_indexes)

    selected_indexes = available_indexes[:30]

    quiz = [
        questions[i]
        for i in selected_indexes
    ]

    history.extend(selected_indexes)

    history = history[-300:]

    user_data["history"] = history

    return quiz

# =========================
# MENULAR
# =========================

def main_menu(user_id):

    buttons = [
        [KeyboardButton("📝 Test ishlash")],
        [KeyboardButton("📊 Natijam")]
    ]

    if is_admin(user_id):

        buttons.append(
            [KeyboardButton("👑 Admin panel")]
        )

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True
    )

def admin_panel():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ User qo‘shish",
                callback_data="add_user"
            )
        ],

        [
            InlineKeyboardButton(
                "🚫 User block",
                callback_data="block_user"
            ),

            InlineKeyboardButton(
                "🔓 Blockdan chiqarish",
                callback_data="unblock_user"
            )
        ],

        [
            InlineKeyboardButton(
                "👥 Userlar",
                callback_data="show_users"
            ),

            InlineKeyboardButton(
                "🚫 Block list",
                callback_data="show_blocked"
            )
        ],

        [
            InlineKeyboardButton(
                "🔍 User qidirish",
                callback_data="search_user"
            )
        ],

        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="stats"
            )
        ],

        [
            InlineKeyboardButton(
                "🧑‍🤝‍🧑 Aktiv userlar",
                callback_data="active_users"
            )
        ]

    ])

# =========================
# START
# =========================

async def start(update: Update,
                context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if is_blocked(user_id):

        await update.message.reply_text(
            "🚫 Siz bloklangansiz."
        )
        return

    if not is_allowed(user_id):

        await update.message.reply_text(
            "⛔ Sizga botdan foydalanish uchun ruxsat berilmagan."
        )
        return

    text = (
        "🎓 Test botiga xush kelibsiz.\n\n"
        "Pastdagi tugmalardan foydalaning."
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu(user_id)
    )

# =========================
# TEST BOSHLASH
# =========================

async def start_test(update,
                     context):

    if not questions:

        await update.message.reply_text(
            "❌ Savollar topilmadi"
        )
        return

    context.user_data["quiz"] = generate_quiz(
        context.user_data
    )

    context.user_data["index"] = 0
    context.user_data["score"] = 0

    await send_question(update, context)

# =========================
# SAVOL YUBORISH
# =========================

async def send_question(update,
                        context):

    index = context.user_data["index"]

    quiz = context.user_data["quiz"]

    if index >= len(quiz):

        score = context.user_data["score"]

        user = update.effective_user

        update_stats(user, score)

        target = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )

        await target.reply_text(
            f"🏁 Test tugadi.\n\n"
            f"✅ Natija: {score}/30",
            reply_markup=main_menu(user.id)
        )

        return

    q = quiz[index]

    context.user_data["current"] = q

    buttons = [
        [
            InlineKeyboardButton(
                "A",
                callback_data="A"
            ),

            InlineKeyboardButton(
                "B",
                callback_data="B"
            ),

            InlineKeyboardButton(
                "C",
                callback_data="C"
            ),

            InlineKeyboardButton(
                "D",
                callback_data="D"
            )
        ]
    ]

    text = (
        f"📘 {index+1}-savol\n\n"
        f"{q['question']}\n\n"
        + "\n".join(q["options"])
    )

    target = (
        update.callback_query.message
        if update.callback_query
        else update.message
    )

    await target.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# =========================
# CALLBACK
# =========================

async def callbacks(update: Update,
                    context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    user_id = update.effective_user.id

    await query.answer()

    # =====================
    # TEST
    # =====================

    if query.data in ["A", "B", "C", "D"]:

        q = context.user_data.get("current")

        if not q:
            return

        correct = q["answer"]

        if query.data == correct:

            context.user_data["score"] += 1

            await query.message.reply_text(
                f"✅ To‘g‘ri ({correct})"
            )

        else:

            await query.message.reply_text(
                f"❌ Noto‘g‘ri ({correct})"
            )

        context.user_data["index"] += 1

        await send_question(update, context)

        return

    # =====================
    # ADMIN
    # =====================

    if not is_admin(user_id):
        return

    if query.data == "stats":

        conn = get_conn()
        cur = conn.cursor()

        total_users = cur.execute("""
        SELECT COUNT(*)
        FROM users
        """).fetchone()[0]

        allowed = cur.execute("""
        SELECT COUNT(*)
        FROM allowed_users
        """).fetchone()[0]

        blocked = cur.execute("""
        SELECT COUNT(*)
        FROM blocked_users
        """).fetchone()[0]

        tests = cur.execute("""
        SELECT SUM(tests_count)
        FROM users
        """).fetchone()[0]

        conn.close()

        tests = tests if tests else 0

        text = (
            f"📊 BOT STATISTIKASI\n\n"
            f"👥 Jami user: {total_users}\n"
            f"✅ Ruxsat berilgan: {allowed}\n"
            f"🚫 Blocklangan: {blocked}\n"
            f"📝 Ishlangan testlar: {tests}"
        )

        await query.message.reply_text(text)

    elif query.data == "active_users":

        conn = get_conn()
        cur = conn.cursor()

        users = cur.execute("""
        SELECT full_name,
               username,
               tests_count,
               last_active
        FROM users
        ORDER BY tests_count DESC
        LIMIT 20
        """).fetchall()

        conn.close()

        if not users:

            await query.message.reply_text(
                "Userlar yo‘q"
            )
            return

        text = "🧑‍🤝‍🧑 Aktiv userlar:\n\n"

        for i, u in enumerate(users, start=1):

            username = (
                f"@{u[1]}"
                if u[1]
                else "username yo‘q"
            )

            text += (
                f"{i}. {u[0]}\n"
                f"{username}\n"
                f"📝 Testlar: {u[2]}\n"
                f"⏰ {u[3]}\n\n"
            )

        await query.message.reply_text(text)

    elif query.data == "add_user":

        context.user_data["mode"] = "add"

        await query.message.reply_text(
            "➕ ID yuboring\n\n"
            "Misol:\n"
            "123456789 987654321"
        )

    elif query.data == "block_user":

        context.user_data["mode"] = "block"

        await query.message.reply_text(
            "🚫 Block qilinadigan ID yuboring"
        )

    elif query.data == "unblock_user":

        context.user_data["mode"] = "unblock"

        await query.message.reply_text(
            "🔓 Blockdan chiqariladigan ID yuboring"
        )

# =========================
# TEXTS
# =========================

async def texts(update: Update,
                context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    text = update.message.text

    mode = context.user_data.get("mode")

    # =====================
    # ADMIN MODES
    # =====================

    if is_admin(user_id) and mode:

        conn = get_conn()
        cur = conn.cursor()

        # ADD

        if mode == "add":

            ids = text.split()

            added = 0

            for uid in ids:

                try:

                    cur.execute("""
                    INSERT OR IGNORE
                    INTO allowed_users(user_id)
                    VALUES(?)
                    """, (int(uid),))

                    added += 1

                except:
                    pass

            conn.commit()
            conn.close()

            context.user_data["mode"] = None

            await update.message.reply_text(
                f"✅ {added} ta user qo‘shildi"
            )

            return

        # BLOCK

        elif mode == "block":

            ids = text.split()

            blocked = 0

            for uid in ids:

                try:

                    uid = int(uid)

                    if uid == ADMIN_ID:
                        continue

                    cur.execute("""
                    INSERT OR IGNORE
                    INTO blocked_users(user_id)
                    VALUES(?)
                    """, (uid,))

                    blocked += 1

                except:
                    pass

            conn.commit()
            conn.close()

            context.user_data["mode"] = None

            await update.message.reply_text(
                f"🚫 {blocked} ta user blocklandi"
            )

            return

        # UNBLOCK

        elif mode == "unblock":

            ids = text.split()

            unblocked = 0

            for uid in ids:

                try:

                    cur.execute("""
                    DELETE FROM blocked_users
                    WHERE user_id=?
                    """, (int(uid),))

                    unblocked += 1

                except:
                    pass

            conn.commit()
            conn.close()

            context.user_data["mode"] = None

            await update.message.reply_text(
                f"🔓 {unblocked} ta user ochildi"
            )

            return

    # =====================
    # MENYU
    # =====================

    if text == "📝 Test ishlash":

        if is_blocked(user_id):

            await update.message.reply_text(
                "🚫 Siz bloklangansiz."
            )
            return

        if not is_allowed(user_id):

            await update.message.reply_text(
                "⛔ Sizga ruxsat berilmagan."
            )
            return

        await start_test(update, context)

    elif text == "📊 Natijam":

        conn = get_conn()
        cur = conn.cursor()

        user = cur.execute("""
        SELECT tests_count,
               total_score,
               best_score,
               last_active
        FROM users
        WHERE user_id=?
        """, (user_id,)).fetchone()

        conn.close()

        if not user:

            await update.message.reply_text(
                "📭 Natija topilmadi"
            )
            return

        avg = 0

        if user[0] > 0:

            avg = round(
                (user[1] / (user[0] * 30)) * 100,
                1
            )

        msg = (
            f"📊 Sizning natijangiz\n\n"
            f"📝 Ishlangan testlar: {user[0]}\n"
            f"🏆 Eng yaxshi natija: {user[2]}/30\n"
            f"📈 O‘rtacha: {avg}%\n"
            f"⏰ Oxirgi aktivlik:\n{user[3]}"
        )

        await update.message.reply_text(msg)

    elif text == "👑 Admin panel":

        if not is_admin(user_id):
            return

        await update.message.reply_text(
            "👑 Admin panel",
            reply_markup=admin_panel()
        )

# =========================
# MAIN
# =========================

if __name__ == "__main__":

    init_db()
    load_questions()

    print("🚀 Bot ishlayapti")

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(callbacks)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            texts
        )
    )

    print("✅ Bot ishga tushdi")

    app.run_polling(
        drop_pending_updates=True
    )
