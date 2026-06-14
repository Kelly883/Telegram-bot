import csv
import html
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import db


# Health check server to prevent Fly.io from stopping the app
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass  # Disable access logging


def start_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

(
    REG_NAME,
    REG_EMAIL,
    REG_PHONE,
    ADMIN_CHOICE,
    ADMIN_LEVEL_NAME,
    ADMIN_LEVEL_PRICE_NGN,
    ADMIN_LEVEL_PRICE_USD,
    ADMIN_LEVEL_DESCRIPTION,
    ADMIN_PREDICTION_TITLE,
    ADMIN_PREDICTION_CONTENT,
    PAYMENT_VERIFY,
    MAIN_MENU,
) = range(12)

PHONE_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def ensure_user_exists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user_by_telegram_id(update.effective_user.id)
    if not user:
        update.message.reply_text(
            "Welcome! Please register first by sending your full name."
        )
        return False
    return True


def format_subscription(subscription):
    if not subscription:
        return (
            "❌ <b>No Active Subscription</b>\n\n"
            "You don't have an active subscription yet!\n\n"
            "Tap 🏠 Back to Menu, then choose 💳 Buy Plan to get started!"
        )
    return (
        "📋 <b>Your Subscription</b>\n\n"
        f"• <b>Plan:</b> {subscription['level_name']}\n"
        f"• <b>Expires:</b> {subscription['expiry_date']}\n"
        f"• <b>Details:</b> {subscription['description']}"
    )


def get_pending_payment_for_user(user_id: int):
    return db.get_pending_payment_by_user(user_id)


def auto_verify_pending_payment(user_id: int):
    payment = get_pending_payment_for_user(user_id)
    if not payment:
        return False
    if verify_gateway_payment(payment):
        db.update_payment_status(payment["tx_ref"], "CONFIRMED")
        expiry_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        db.create_subscription(payment["user_id"], payment["level_id"], expiry_date)
        return True
    return False


def get_welcome_menu(is_admin_user: bool = False) -> str:
    text = (
        "🎉 <b>Welcome to PredictPro Bot!</b> 🎉\n\n"
        "Get access to exclusive predictions with just a few taps!\n\n"
        "• 🔄 Auto payment verification\n"
        "• 📱 Instant access on Telegram\n"
        "• 💎 Premium predictions\n\n"
        "👇 Send your full name to start your registration journey!"
    )
    if is_admin_user:
        text += "\n\n<b>Admin Tip:</b> Use /admin to manage your bot!"
    return text


def get_user_menu_keyboard(telegram_user_id: int) -> InlineKeyboardMarkup:
    """Create an interactive menu keyboard for registered users"""
    keyboard = [
        [InlineKeyboardButton("📋 My Subscription", callback_data="menu:my_sub"),
         InlineKeyboardButton("💳 Buy Plan", callback_data="menu:subscribe")],
        [InlineKeyboardButton("🔮 View Predictions", callback_data="menu:predictions"),
         InlineKeyboardButton("🔄 Extend Plan", callback_data="menu:extend")],
        [InlineKeyboardButton("❓ Help & Support", callback_data="menu:help")],
    ]
    if is_admin(telegram_user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="menu:admin")])
    return InlineKeyboardMarkup(keyboard)


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Create admin menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Create Plan", callback_data="admin:create_plan"),
         InlineKeyboardButton("📊 View Users", callback_data="admin:view_users")],
        [InlineKeyboardButton("📝 Add Prediction", callback_data="admin:add_pred"),
         InlineKeyboardButton("📋 View Plans", callback_data="admin:view_plans")],
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button callbacks"""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    user_id = query.from_user.id
    user = db.get_user_by_telegram_id(user_id)
    
    if not user:
        keyboard = [[InlineKeyboardButton("🏠 Go to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(
            "⚠️ Please register first using /start!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if action == "my_sub":
        subscription = db.get_active_subscription(user["id"])
        text = format_subscription(subscription)
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "subscribe":
        levels = db.list_subscription_plans()
        if not levels:
            keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
            await query.edit_message_text(
                "📭 No subscription plans available yet.\nPlease check back later!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return
        keyboard = []
        for level in levels:
            price_text = format_price_for_user(level, user)
            keyboard.append([InlineKeyboardButton(f"💳 {level['name']} - {price_text}", callback_data=f"subscribe:{level['id']}")])
        keyboard.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")])
        await query.edit_message_text(
            "🎯 <b>Choose Your Subscription Plan</b>\n\nPick a plan that fits your needs!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    
    elif action == "predictions":
        subscription = db.get_active_subscription(user["id"])
        if not subscription:
            keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back"),
                         InlineKeyboardButton("💳 Buy a Plan", callback_data="menu:subscribe")]]
            await query.edit_message_text(
                "❌ You don't have an active subscription to view predictions!\n\nPlease purchase a plan first.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return
        predictions = db.list_predictions_for_plan(subscription["level_id"])
        if not predictions:
            keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
            await query.edit_message_text(
                "🔮 No predictions available for your subscription plan yet.\nCheck back soon!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return
        text = "🔮 <b>Latest Predictions</b>\n\n"
        for pred in predictions[:10]:
            text += f"📌 <b>{html.escape(pred['title'])}</b>\n{html.escape(pred['content'])}\n\n"
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    elif action == "extend":
        levels = db.list_subscription_plans()
        if not levels:
            keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
            await query.edit_message_text(
                "📭 No subscription plans available yet.\nPlease check back later!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return
        keyboard = []
        for level in levels:
            price_text = format_price_for_user(level, user)
            keyboard.append([InlineKeyboardButton(f"💳 {level['name']} - {price_text}", callback_data=f"subscribe:{level['id']}")])
        keyboard.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")])
        await query.edit_message_text(
            "🔄 <b>Extend Your Subscription</b>\n\nChoose a plan to renew your subscription!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    
    elif action == "admin":
        if is_admin(user_id):
            await query.edit_message_text(
                "⚙️ <b>Admin Panel</b> - Choose an action:",
                reply_markup=get_admin_menu_keyboard(),
                parse_mode="HTML"
            )
        else:
            keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
            await query.edit_message_text(
                "❌ You don't have admin access.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif action == "help":
        help_text = (
            "❓ <b>Need help?</b> No worries!\n\n"
            "Here's what you can do:\n\n"
            "1. 📋 <b>My Subscription</b> - Check your current subscription status\n"
            "2. 💳 <b>Buy Plan</b> - Purchase a new subscription\n"
            "3. 🔮 <b>View Predictions</b> - See premium predictions\n"
            "4. 🔄 <b>Extend Plan</b> - Renew your subscription\n\n"
            "Just tap the buttons to get started!"
        )
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(help_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "back":
        subscription = db.get_active_subscription(user["id"])
        sub_text = f"✅ <b>Active:</b> {subscription['level_name']}" if subscription else "❌ <b>No active subscription</b>"
        welcome_msg = (
            f"👋 <b>Welcome back, {html.escape(user['name'])}!</b>\n"
            f"{sub_text}\n\n"
            "What would you like to do today?"
        )
        await query.edit_message_text(welcome_msg, parse_mode="HTML", reply_markup=get_user_menu_keyboard(user_id))




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user_by_telegram_id(user_id)
    
    if not user:
        welcome_text = get_welcome_menu(is_admin(user_id))
        await update.message.reply_text(welcome_text, parse_mode="HTML")
        await update.message.reply_text("To register, please send your full name.")
        return REG_NAME
    
    # Registered user: show interactive menu
    verified = auto_verify_pending_payment(user["id"])
    if verified:
        await update.message.reply_text(
            "✅ Your pending payment was verified automatically and your subscription is now active."
        )
    
    subscription = db.get_active_subscription(user["id"])
    sub_text = f"✅ <b>Active:</b> {subscription['level_name']}" if subscription else "❌ <b>No active subscription</b>"
    welcome_msg = (
        f"👋 <b>Welcome back, {html.escape(user['name'])}!</b>\n"
        f"{sub_text}\n\n"
        "Tap a button below to continue."
    )
    
    await update.message.reply_text(
        welcome_msg,
        reply_markup=get_user_menu_keyboard(user_id),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["register_name"] = update.message.text.strip()
    await update.message.reply_text("Great! Please send your email address.")
    return REG_EMAIL


async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email or "." not in email:
        await update.message.reply_text("Please send a valid email address.")
        return REG_EMAIL
    context.user_data["register_email"] = email
    await update.message.reply_text(
        "Now send your phone number including country code, for example +2348012345678."
    )
    return REG_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not PHONE_PATTERN.match(phone):
        await update.message.reply_text(
            "Phone must include country code and only digits, for example +2348012345678."
        )
        return REG_PHONE
    name = context.user_data["register_name"]
    email = context.user_data["register_email"]
    country_code = phone[1:4] if len(phone) >= 4 else phone[1:]
    db.create_user(update.effective_user.id, name, email, phone, country_code)
    user = db.get_user_by_telegram_id(update.effective_user.id)
    welcome_msg = (
        f"👋 <b>Welcome, {html.escape(user['name'])}!</b>\n"
        "❌ <b>No active subscription</b>\n\n"
        "Tap a button below to continue."
    )
    await update.message.reply_text(
        welcome_msg,
        reply_markup=get_user_menu_keyboard(update.effective_user.id),
        parse_mode="HTML"
    )
    return ConversationHandler.END


def is_nigerian(user: dict) -> bool:
    return bool(user and user.get("country_code", "").startswith("234"))


def format_price_for_user(level: dict, user: dict) -> str:
    if is_nigerian(user):
        return f"NGN{level['price_ngn']}"
    return f"USD{level['price_usd']}"


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text(
            "⚠️ Please register first using /start to continue!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Go to Main Menu", callback_data="menu:back")]])
        )
        return ConversationHandler.END
    levels = db.list_subscription_plans()
    if not levels:
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await update.message.reply_text(
            "📭 No subscription plans available yet.\nPlease check back later or contact support!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    keyboard = []
    for level in levels:
        price_text = format_price_for_user(level, user)
        keyboard.append(
            [InlineKeyboardButton(f"💳 {level['name']} - {price_text}", callback_data=f"subscribe:{level['id']}")]
        )
    keyboard.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")])
    await update.message.reply_text(
        "🎯 <b>Choose Your Subscription Plan</b>\n\nPick a plan that fits your needs!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, level_id = query.data.split(":")
    level = db.get_subscription_plan(int(level_id))
    user = db.get_user_by_telegram_id(query.from_user.id)
    if not level or not user:
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(
            "❌ Oops! Could not find the subscription plan or your profile.\nPlease try again later!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    currency = "NGN" if user["country_code"].startswith("234") else "USD"
    amount = level["price_ngn"] if currency == "NGN" else level["price_usd"]
    gateway = "PAYSTACK" if currency == "NGN" else "FLUTTERWAVE"
    tx_ref = f"SUB-{uuid.uuid4().hex[:12]}"
    payment_url = create_payment_link(user, level, amount, currency, gateway, tx_ref)
    if not payment_url:
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(
            "❌ Failed to generate payment link. Please try again later!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    db.record_payment(user["id"], level["id"], gateway, tx_ref, amount, currency, "PENDING")
    
    # Add verify button and back to menu button
    keyboard = [
        [InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_pay:{tx_ref}")],
        [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")],
    ]
    
    await query.edit_message_text(
        f"💎 <b>Complete Your Payment for {level['name']}</b>\n\n"
        f"👉 Pay here: {payment_url}\n\n"
        f"✅ Payment auto-checking is active\n"
        f"⏱️ You'll get a notification once your payment is confirmed!\n\n"
        f"Tap \"Verify Payment\" if you need to check manually!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def create_payment_link(user, level, amount, currency, gateway, tx_ref):
    if gateway == "PAYSTACK":
        return create_paystack_payment(user, amount, currency, tx_ref)
    return create_flutterwave_payment(user, amount, currency, tx_ref)


def create_paystack_payment(user, amount, currency, tx_ref):
    url = "https://api.paystack.co/transaction/initialize"
    payload = {
        "email": user["email"],
        "amount": int(amount) * 100,
        "currency": currency,
        "reference": tx_ref,
        "callback_url": config.PAYMENT_CALLBACK_URL or "",
    }
    headers = {
        "Authorization": f"Bearer {config.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    data = response.json()
    return data.get("data", {}).get("authorization_url") if data.get("status") else None


def create_flutterwave_payment(user, amount, currency, tx_ref):
    url = "https://api.flutterwave.com/v3/payments"
    payload = {
        "tx_ref": tx_ref,
        "amount": str(amount),
        "currency": currency,
        "redirect_url": config.PAYMENT_CALLBACK_URL or "",
        "customer": {
            "email": user["email"],
            "phonenumber": user["phone"],
            "name": user["name"],
        },
    }
    headers = {
        "Authorization": f"Bearer {config.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    data = response.json()
    return data.get("data", {}).get("link") if data.get("status") == "success" else None


async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Manual verification is no longer required.\n\n"
        "Use the button on your payment screen or wait a few seconds for auto-verification.\n"
        "If your payment is still pending, you can retry the button after a moment."
    )


async def verify_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment verification button click"""
    query = update.callback_query
    await query.answer()
    
    _, tx_ref = query.data.split(":")
    payment = db.get_payment_by_ref(tx_ref)
    
    if not payment:
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(
            "❌ Payment record not found.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    
    if payment["status"] == "CONFIRMED":
        keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
        await query.edit_message_text(
            "✅ This payment has already been confirmed and your subscription is active!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    
    # Attempt to verify payment
    await query.edit_message_text("⏳ Verifying payment with payment gateway...", parse_mode="HTML")
    
    verification = verify_gateway_payment(payment)
    if not verification:
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data=f"verify_pay:{tx_ref}")],
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]
        ]
        await query.edit_message_text(
            "❌ Payment not confirmed yet.\n\n"
            "This might be because:\n"
            "• Payment is still processing\n"
            "• Payment amount doesn't match\n"
            "• Email mismatch\n\n"
            "Try again in a moment or check with your payment provider.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    
    # Payment verified successfully
    db.update_payment_status(tx_ref, "CONFIRMED")
    expiry_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    db.create_subscription(payment["user_id"], payment["level_id"], expiry_date)
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="menu:back")]]
    await query.edit_message_text(
        "✅ Payment confirmed!\n\n"
        "Your subscription is now active. You'll receive notifications about new predictions.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


def verify_gateway_payment(payment):
    """
    Enhanced verification with fraud detection:
    - Validates gateway response
    - Checks amount matches subscription price
    - Validates transaction timestamp
    - Logs all verification attempts
    """
    fraud_flags = []
    amount_match = True
    timestamp_valid = True
    gateway_response = None
    verification_result = False

    try:
        # Get subscription level to validate amount
        level = db.get_subscription_plan(payment["level_id"])
        expected_amount = level["price_ngn"] if payment["currency"] == "NGN" else level["price_usd"]
        
        # Check 1: Amount Verification
        if payment["amount"] != expected_amount:
            fraud_flags.append(f"AMOUNT_MISMATCH|expected:{expected_amount}|paid:{payment['amount']}")
            amount_match = False
        
        # Check 2: Transaction Timestamp Validation (not older than 24 hours)
        payment_time = datetime.fromisoformat(payment["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        time_diff = datetime.now(timezone.utc) - payment_time
        if time_diff.total_seconds() > 86400:  # 24 hours
            fraud_flags.append(f"TRANSACTION_TOO_OLD|age_hours:{time_diff.total_seconds() / 3600}")
            timestamp_valid = False
        
        # Call appropriate gateway
        if payment["gateway"] == "PAYSTACK":
            verification_result, gateway_response = verify_paystack_payment_enhanced(payment["tx_ref"], payment)
        else:
            verification_result, gateway_response = verify_flutterwave_payment_enhanced(payment["tx_ref"], payment)
        
        # Additional fraud checks
        if verification_result and gateway_response:
            # Check 3: Verify customer email matches (if available)
            gw_email = gateway_response.get("email") or gateway_response.get("customer", {}).get("email")
            payment_user = db.get_user_by_id(payment["user_id"])
            if gw_email and payment_user and payment_user["email"].lower() != gw_email.lower():
                fraud_flags.append(f"EMAIL_MISMATCH|gateway:{gw_email}|local:{payment_user['email']}")
            
            # Check 4: Verify amount from gateway matches
            gw_amount = gateway_response.get("amount") or gateway_response.get("data", {}).get("amount")
            if gw_amount and gw_amount != payment["amount"]:
                fraud_flags.append(f"GATEWAY_AMOUNT_MISMATCH|gateway:{gw_amount}|local:{payment['amount']}")
        
        # Log the verification attempt
        db.log_verification_attempt(
            payment["id"],
            payment["tx_ref"],
            "SUCCESS" if verification_result else "FAILED",
            str(gateway_response)[:500] if gateway_response else None,
            amount_match,
            timestamp_valid,
            fraud_flags
        )
        
    except Exception as e:
        fraud_flags.append(f"VERIFICATION_ERROR:{str(e)}")
        db.log_verification_attempt(
            payment["id"],
            payment["tx_ref"],
            "ERROR",
            str(e)[:500],
            False,
            False,
            fraud_flags
        )
        return False
    
    # Return True only if gateway verified AND all fraud checks passed
    return verification_result and amount_match and timestamp_valid and not fraud_flags


def verify_paystack_payment_enhanced(tx_ref: str, payment: dict):
    """Verify with Paystack and return (success: bool, response: dict)"""
    try:
        url = f"https://api.paystack.co/transaction/verify/{tx_ref}"
        headers = {"Authorization": f"Bearer {config.PAYSTACK_SECRET_KEY}"}
        response = requests.get(url, headers=headers, timeout=2)
        data = response.json()
        
        if not data.get("status"):
            return False, data
        
        tx_data = data.get("data", {})
        is_successful = tx_data.get("status") in ("success", "paid")
        return is_successful, tx_data
    except Exception as e:
        return False, {"error": str(e)}


def verify_flutterwave_payment_enhanced(tx_ref: str, payment: dict):
    """Verify with Flutterwave and return (success: bool, response: dict)"""
    try:
        url = f"https://api.flutterwave.com/v3/transactions/verify_by_tx_ref?tx_ref={tx_ref}"
        headers = {"Authorization": f"Bearer {config.FLUTTERWAVE_SECRET_KEY}"}
        response = requests.get(url, headers=headers, timeout=2)
        data = response.json()
        
        if data.get("status") != "success":
            return False, data
        
        tx_data = data.get("data", {})
        is_successful = tx_data.get("status") == "successful"
        return is_successful, tx_data
    except Exception as e:
        return False, {"error": str(e)}


async def my_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please register first with /start.")
        return
    subscription = db.get_active_subscription(user["id"])
    await update.message.reply_text(
        format_subscription(subscription), 
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Menu", callback_data="menu:back")]])
    )


async def show_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please register first with /start.")
        return
    subscription = db.get_active_subscription(user["id"])
    if not subscription:
        await update.message.reply_text("You do not have an active subscription. Use /subscribe to buy a plan.")
        return
    predictions = db.list_predictions_for_plan(subscription["level_id"])
    if not predictions:
        await update.message.reply_text("No predictions yet for your subscription level.")
        return
    texts = [f"*{html.escape(pred['title'])}*\n{html.escape(pred['content'])}" for pred in predictions]
    await update.message.reply_text("\n\n".join(texts), parse_mode="HTML")


async def extend_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await subscribe(update, context)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized. Only admins may use this command.")
        return
    print(f"DEBUG: Admin command called by user {update.effective_user.id}")
    keyboard = [
        [InlineKeyboardButton("💎 Create Subscription Plan", callback_data="admin:create_level")],
        [InlineKeyboardButton("📤 Upload Prediction", callback_data="admin:upload_prediction")],
        [InlineKeyboardButton("👥 View All Users", callback_data="admin:view_users")],
        [InlineKeyboardButton("📥 Download Users CSV", callback_data="admin:download_users")],
    ]
    welcome_msg = (
        "🔐 <b>Admin Control Panel</b>\n\n"
        "Welcome to the admin dashboard! Use the buttons below to manage your bot.\n\n"
        "• Create new subscription plans\n"
        "• Upload predictions for subscribers\n"
        "• View and download user data"
    )
    await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    print(f"DEBUG: Admin callback received, data={repr(query.data)}")
    action = query.data.split(":", 1)[1]
    print(f"DEBUG: Extracted action={repr(action)}")
    if action == "create_level":
        await query.edit_message_text(
            "💎 Let's create a new subscription plan!\n\n"
            "Please send the <b>plan name</b> (e.g., Gold Membership):",
            parse_mode="HTML"
        )
        return ADMIN_LEVEL_NAME
    if action == "upload_prediction":
        levels = db.list_subscription_plans()
        if not levels:
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin:back")]]
            await query.edit_message_text(
                "❌ No subscription plans defined yet! Create a plan first using \"Create Subscription Plan\".",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(f"💎 {level['name']}", callback_data=f"admin_level:{level['id']}")] for level in levels]
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin:back")])
        await query.edit_message_text(
            "📤 Upload a new prediction\n\n"
            "Which subscription level should this prediction be for?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return ADMIN_CHOICE
    if action == "view_users":
        users = db.list_users()
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin:back")]]
        if users:
            lines = [
                f"👤 <b>{html.escape(u['name'])}</b>\n"
                f"   📧 {u['email']}\n"
                f"   📱 {u['phone']}\n"
                f"   📅 Joined: {u['created_at']}\n"
                for u in users
            ]
            message = "👥 <b>All Users</b>\n\n" + "\n".join(lines)
        else:
            message = "👥 <b>All Users</b>\n\nNo users yet!"
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return ConversationHandler.END
    if action == "download_users":
        path = db.export_users_csv("users_export.csv")
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin:back")]]
        await query.edit_message_text(
            f"✅ Users exported successfully to <code>{path}</code>!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    if action == "back":
        # Send back to admin panel
        keyboard = [
            [InlineKeyboardButton("💎 Create Subscription Plan", callback_data="admin:create_level")],
            [InlineKeyboardButton("📤 Upload Prediction", callback_data="admin:upload_prediction")],
            [InlineKeyboardButton("👥 View All Users", callback_data="admin:view_users")],
            [InlineKeyboardButton("📥 Download Users CSV", callback_data="admin:download_users")],
        ]
        welcome_msg = (
            "🔐 <b>Admin Control Panel</b>\n\n"
            "Welcome to the admin dashboard! Use the buttons below to manage your bot.\n\n"
            "• Create new subscription plans\n"
            "• Upload predictions for subscribers\n"
            "• View and download user data"
        )
        await query.edit_message_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin:back")]]
    await query.edit_message_text(f"❌ Unknown admin action: {repr(action)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


async def admin_level_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["admin_level_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Great! Now send the <b>price in NGN</b> (Nigerian Naira):",
        parse_mode="HTML"
    )
    return ADMIN_LEVEL_PRICE_NGN


async def admin_level_price_ngn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "❌ Please send a valid numeric price (only digits, no commas or currency symbols)!",
            parse_mode="HTML"
        )
        return ADMIN_LEVEL_PRICE_NGN
    context.user_data["admin_level_price_ngn"] = int(text)
    await update.message.reply_text(
        "Perfect! Now send the <b>price in USD</b> (US Dollars):",
        parse_mode="HTML"
    )
    return ADMIN_LEVEL_PRICE_USD


async def admin_level_price_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "❌ Please send a valid numeric price (only digits, no commas or currency symbols)!",
            parse_mode="HTML"
        )
        return ADMIN_LEVEL_PRICE_USD
    context.user_data["admin_level_price_usd"] = int(text)
    await update.message.reply_text(
        "Almost done! Send a <b>short description</b> for this subscription plan:",
        parse_mode="HTML"
    )
    return ADMIN_LEVEL_DESCRIPTION


async def admin_level_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["admin_level_name"]
    price_ngn = context.user_data["admin_level_price_ngn"]
    price_usd = context.user_data["admin_level_price_usd"]
    description = update.message.text.strip()
    db.create_subscription_plan(name, price_ngn, price_usd, description)
    await update.message.reply_text(
        "✅ <b>Subscription Plan Created Successfully!</b>\n\n"
        f"💎 Plan Name: {html.escape(name)}\n"
        f"💰 NGN Price: {price_ngn}\n"
        f"💰 USD Price: {price_usd}\n"
        f"📝 Description: {html.escape(description)}",
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, level_id = query.data.split(":")
    level = db.get_subscription_plan(int(level_id))
    context.user_data["admin_prediction_level_id"] = int(level_id)
    await query.edit_message_text(
        f"📤 Uploading prediction for <b>{html.escape(level['name'])}</b>\n\n"
        "Please send the <b>prediction title</b>:",
        parse_mode="HTML"
    )
    return ADMIN_PREDICTION_TITLE


async def admin_prediction_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["admin_prediction_title"] = update.message.text.strip()
    await update.message.reply_text(
        "Perfect! Now send the <b>full prediction content</b>:",
        parse_mode="HTML"
    )
    return ADMIN_PREDICTION_CONTENT


async def admin_prediction_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data["admin_prediction_title"]
    content = update.message.text.strip()
    level_id = context.user_data["admin_prediction_level_id"]
    db.add_prediction(level_id, title, content)
    level = db.get_subscription_plan(level_id)
    await update.message.reply_text(
        "✅ <b>Prediction Saved Successfully!</b>\n\n"
        f"💎 Plan: {html.escape(level['name'])}\n"
        f"📌 Title: {html.escape(title)}\n"
        f"Notifying subscribers now...",
        parse_mode="HTML"
    )
    notify_subscribers(level_id, title, content)
    return ConversationHandler.END


def notify_subscribers(level_id: int, title: str, content: str):
    subscription_users = []
    with db.get_connection() as conn:
        if hasattr(conn, 'cursor'):  # Postgres
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT u.telegram_id FROM subscriptions s JOIN users u ON s.user_id = u.id "
                    "WHERE s.level_id = %s AND s.active = 1",
                    (level_id,),
                )
                rows = cur.fetchall()
                subscription_users = [row["telegram_id"] for row in rows]
        else:  # SQLite
            rows = conn.execute(
                "SELECT u.telegram_id FROM subscriptions s JOIN users u ON s.user_id = u.id "
                "WHERE s.level_id = ? AND s.active = 1",
                (level_id,),
            ).fetchall()
            subscription_users = [row["telegram_id"] for row in rows]
    
    text = (
        f"📢 <b>New Prediction Available!</b>\n\n"
        f"📌 {html.escape(title)}\n\n"
        f"{html.escape(content)}"
    )
    from telegram import Bot
    bot = Bot(token=config.BOT_TOKEN)
    for telegram_id in subscription_users:
        try:
            bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        except Exception:
            continue


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation canceled.")
    return ConversationHandler.END


def process_pending_payments(bot):
    """Verify pending payments automatically in the background."""
    payments = db.get_all_pending_payments()
    for payment in payments:
        # Check if transaction is older than 24 hours
        payment_time = datetime.fromisoformat(payment["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        time_diff = datetime.now(timezone.utc) - payment_time
        if time_diff.total_seconds() > 86400:
            db.update_payment_status(payment["tx_ref"], "EXPIRED")
            continue

        if verify_gateway_payment(payment):
            try:
                db.update_payment_status(payment["tx_ref"], "CONFIRMED")
                expiry_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
                db.create_subscription(payment["user_id"], payment["level_id"], expiry_date)

                user = db.get_user_by_id(payment["user_id"])
                level = db.get_subscription_plan(payment["level_id"])
                try:
                    bot.send_message(
                        chat_id=user["telegram_id"],
                        text=(
                            f"✅ Great news! Your payment for {level['name']} has been automatically verified and your subscription is now active!\n\n"
                            "Enjoy your access to exclusive predictions."
                        ),
                    )
                except Exception as e:
                    print(f"Failed to notify user {user['telegram_id']}: {e}")
            except Exception as e:
                print(f"Error processing payment {payment['tx_ref']}: {e}")


def start_payment_verification_thread(bot):
    while True:
        try:
            process_pending_payments(bot)
        except Exception as e:
            print(f"Background payment verification error: {e}")
        time.sleep(2)


async def check_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    """Background job to verify pending payments automatically"""
    process_pending_payments(context.bot)


def main():
    # Start health check server first
    start_health_server()
    db.init_db()
    application = Application.builder().token(config.BOT_TOKEN).build()
    registration = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REG_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_email)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    admin_flow = ConversationHandler(
        entry_points=[CommandHandler("admin", admin), CallbackQueryHandler(admin_callback, pattern=r"^admin:")],
        states={
            ADMIN_LEVEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_level_name)],
            ADMIN_LEVEL_PRICE_NGN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_level_price_ngn)],
            ADMIN_LEVEL_PRICE_USD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_level_price_usd)],
            ADMIN_LEVEL_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_level_description)],
            ADMIN_CHOICE: [CallbackQueryHandler(admin_choice, pattern=r"^admin_level:")],
            ADMIN_PREDICTION_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_prediction_title)],
            ADMIN_PREDICTION_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_prediction_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    application.add_handler(registration)
    application.add_handler(admin_flow)
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^menu:"))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CallbackQueryHandler(subscribe_callback, pattern=r"^subscribe:"))
    application.add_handler(CallbackQueryHandler(verify_payment_callback, pattern=r"^verify_pay:"))
    application.add_handler(CommandHandler("verify_payment", verify_payment))
    application.add_handler(CommandHandler("my_subscription", my_subscription))
    application.add_handler(CommandHandler("predictions", show_predictions))
    application.add_handler(CommandHandler("extend", extend_subscription))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Schedule background payment verification every 2 seconds
    job_queue = application.job_queue
    if job_queue is not None:
        job_queue.run_repeating(check_pending_payments, interval=2, first=1)
    else:
        print("Warning: JobQueue unavailable; using thread-based payment verification.")
        threading.Thread(target=start_payment_verification_thread, args=(application.bot,), daemon=True).start()

    application.run_polling()


if __name__ == "__main__":
    main()
