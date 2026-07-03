import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables!")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("No GEMINI_API_KEY found in environment variables!")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Use a model that's available in the free tier
# Options: "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-lite"
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("✅ Using gemini-1.5-flash model")
except Exception as e:
    logger.error(f"❌ Error loading model: {e}")
    # Fallback to a simpler model
    model = genai.GenerativeModel('gemini-pro')
    logger.info("✅ Using gemini-pro model")

# Conversation states
CHOOSING_ACTION, AWAITING_TEXT, AWAITING_PUBLISH = range(3)

# User preferences storage (in-memory, resets on restart)
user_data_store = {}

# Language settings
LANGUAGES = {
    "en": "English",
    "ru": "Russian"
}

# ==================== AI HELPER FUNCTIONS ====================

def get_ai_response(prompt: str, instruction: str) -> str:
    """Send prompt to Gemini AI and get response."""
    try:
        full_prompt = f"{instruction}\n\nUser text:\n{prompt}"
        response = model.generate_content(full_prompt)
        return response.text.strip() if response.text else "⚠️ No response generated. Please try again."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return f"❌ AI Error: {str(e)}"

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the bot and show main menu."""
    user = update.effective_user
    user_id = user.id

    # Initialize user data
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "language": "en",
            "history": []
        }

    welcome_text = (
        f"✍️ **Hello {user.first_name}!**\n\n"
        "I'm your **AI Writing Assistant**! I can help you with:\n\n"
        "📝 **Create** - Generate content from a topic\n"
        "✨ **Improve** - Enhance your existing text\n"
        "🔧 **Fix Errors** - Correct grammar and spelling\n"
        "📊 **Analyze** - Get detailed recommendations\n"
        "✂️ **Shorten** - Make text more concise\n"
        "📝 **Expand** - Add more details and examples\n"
        "🌐 **Translate** - Translate to another language\n\n"
        "Select an action from the menu below 👇"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Create Post", callback_data="create")],
        [InlineKeyboardButton("✨ Improve Text", callback_data="improve")],
        [InlineKeyboardButton("🔧 Fix Errors", callback_data="fix")],
        [InlineKeyboardButton("✂️ Shorten", callback_data="shorten")],
        [InlineKeyboardButton("📝 Expand", callback_data="expand")],
        [InlineKeyboardButton("📊 Analyze", callback_data="analyze")],
        [InlineKeyboardButton("🌐 Translate", callback_data="translate")],
        [InlineKeyboardButton("📢 Publish to Channel", callback_data="publish")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    return CHOOSING_ACTION

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    help_text = (
        "📖 **Help & Commands**\n\n"
        "• /start - Show main menu\n"
        "• /help - Show this help\n"
        "• /cancel - Cancel current operation\n\n"
        "**How to use:**\n"
        "1️⃣ Select an action from the menu\n"
        "2️⃣ Send your text or topic\n"
        "3️⃣ Receive AI-enhanced content\n"
        "4️⃣ Publish directly to your channel (optional)\n\n"
        "**Writing Tips:**\n"
        "• Be specific about what you need\n"
        "• Provide context for better results\n"
        "• Request multiple iterations if needed"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel current operation."""
    await update.message.reply_text("✅ Operation cancelled. Use /start to begin again.")
    return ConversationHandler.END

# ==================== ACTION HANDLERS ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle menu button clicks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    action = query.data

    # Store the action in context
    context.user_data['action'] = action

    action_messages = {
        "create": "📝 **Create Post**\n\nSend me a topic or description, and I'll generate a post for you.",
        "improve": "✨ **Improve Text**\n\nSend me your text and I'll enhance its structure, readability, and engagement.",
        "fix": "🔧 **Fix Errors**\n\nSend me your text and I'll correct grammar, spelling, and punctuation.",
        "shorten": "✂️ **Shorten**\n\nSend me your text and I'll make it more concise.",
        "expand": "📝 **Expand**\n\nSend me your text and I'll add more details and examples.",
        "analyze": "📊 **Analyze**\n\nSend me your text and I'll provide detailed improvement recommendations.",
        "translate": "🌐 **Translate**\n\nSend me your text and I'll translate it to your preferred language.",
        "publish": "📢 **Publish to Channel**\n\nSend me the text you want to publish. Make sure I'm an admin in your channel!",
        "help": "❓ **Help**\n\nUse /help for assistance."
    }

    if action == "help":
        await query.message.edit_text(action_messages["help"], parse_mode="Markdown")
        return ConversationHandler.END

    await query.message.edit_text(action_messages.get(action, "⚠️ Unknown action. Please try again."), parse_mode="Markdown")
    await query.message.reply_text("📤 **Send me your text now:**", parse_mode="Markdown")

    return AWAITING_TEXT

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process user text based on selected action."""
    user_id = update.effective_user.id
    user_text = update.message.text
    action = context.user_data.get('action', 'improve')

    # Send typing indicator
    await update.message.chat.send_action(action="typing")

    # Define instructions for each action
    instructions = {
        "create": "You are a professional content creator. Generate a well-structured, engaging post based on this topic. Use markdown formatting for headings and lists.",
        "improve": "You are a professional editor. Improve this text's structure, readability, clarity, and engagement. Fix any issues but keep the original meaning.",
        "fix": "You are a proofreader. Fix all grammar, spelling, and punctuation errors. Keep the original meaning and tone.",
        "shorten": "You are a conciseness expert. Make this text more concise while keeping all key information. Remove redundancy and fluff.",
        "expand": "You are a content expander. Add more details, examples, and depth to this text. Make it more comprehensive.",
        "analyze": "You are a content analyst. Provide detailed recommendations for improving this text. Include structure, style, engagement, and SEO suggestions.",
        "translate": "You are a professional translator. Translate this text to English (or ask user for language preference). Keep the original meaning and tone.",
        "publish": "You are a content optimizer. Clean and format this text for publication. Ensure it's polished and ready to share."
    }

    instruction = instructions.get(action, "You are a helpful AI writing assistant. Help the user with their text.")

    # Get AI response
    response = get_ai_response(user_text, instruction)

    if response and not response.startswith("❌ AI Error"):
        # Truncate if too long (Telegram limit is 4096 characters)
        if len(response) > 4000:
            response = response[:3997] + "..."

        keyboard = [
            [InlineKeyboardButton("✍️ Try Another Action", callback_data="new_action")],
            [InlineKeyboardButton("📢 Publish", callback_data="publish_this")],
            [InlineKeyboardButton("🔄 Regenerate", callback_data="regenerate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✍️ **AI Writing Assistant Result:**\n\n{response}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        # Store for publishing
        context.user_data['last_response'] = response
    else:
        await update.message.reply_text("❌ I couldn't process that. Please try again or use /cancel to start over.")

    return CHOOSING_ACTION

async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle post-action buttons."""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "new_action":
        await query.message.reply_text("✍️ Select a new action:", reply_markup=get_main_menu())
        return CHOOSING_ACTION

    elif action == "publish_this":
        text = context.user_data.get('last_response', '')
        if text:
            await query.message.reply_text(
                "📢 **Publishing ready!**\n\n"
                "To publish to a channel:\n"
                "1. Make me an admin in your channel\n"
                "2. Send: /publish @channel_username\n\n"
                "Or send me the text again to publish."
            )
        return CHOOSING_ACTION

    elif action == "regenerate":
        # User needs to send text again
        await query.message.reply_text("📤 **Send your text again for a new response:**")
        return AWAITING_TEXT

    return CHOOSING_ACTION

# ==================== PUBLISH HANDLER ====================

async def publish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Publish content to a channel."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "📢 **Publish Command**\n\n"
            "Usage: /publish @channel_username\n\n"
            "Make sure I'm an admin in the channel first!"
        )
        return

    channel = args[0]
    text = context.user_data.get('last_response', '')

    if not text:
        await update.message.reply_text("❌ No content to publish. Generate or improve some text first!")
        return

    try:
        await context.bot.send_message(chat_id=channel, text=text, parse_mode="Markdown")
        await update.message.reply_text(f"✅ Content published successfully to {channel}!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to publish: {str(e)}\n\nMake sure I'm an admin in the channel!")

# ==================== UTILITY FUNCTIONS ====================

def get_main_menu():
    """Return main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("📝 Create Post", callback_data="create")],
        [InlineKeyboardButton("✨ Improve Text", callback_data="improve")],
        [InlineKeyboardButton("🔧 Fix Errors", callback_data="fix")],
        [InlineKeyboardButton("✂️ Shorten", callback_data="shorten")],
        [InlineKeyboardButton("📝 Expand", callback_data="expand")],
        [InlineKeyboardButton("📊 Analyze", callback_data="analyze")],
        [InlineKeyboardButton("🌐 Translate", callback_data="translate")],
        [InlineKeyboardButton("📢 Publish to Channel", callback_data="publish")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    await update.message.reply_text(
        "❌ Unknown command. Use /start to see the menu or /help for assistance."
    )

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again or use /help for assistance."
            )
    except:
        pass

# ==================== MAIN FUNCTION ====================

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_ACTION: [
                CallbackQueryHandler(button_callback),
                CommandHandler("start", start),
            ],
            AWAITING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                CallbackQueryHandler(action_callback),
                CommandHandler("cancel", cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("publish", publish_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("✍️ AI Writing Assistant Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
