# Telegram Subscription Bot

A subscription-based Telegram bot where:

- Admins can create subscription tiers and upload predictions per tier
- Users register with name, email, and phone number (+country code required)
- Users receive push notifications when new predictions are published for their active tier
- Users can extend subscriptions
- Users get payment links in the bot via Flutterwave and Paystack
- Nigerian users pay in Naira, other users pay in USD

## Features

- Admin commands:
  - `/admin` - open admin control panel
  - create subscription levels
  - upload predictions for each subscription level
  - view user details
  - download users details as CSV
- User commands:
  - `/start` - register or return to menu
  - `/subscribe` - buy a subscription tier
  - `/extend` - extend an existing subscription
  - `/my_subscription` - view current subscription status
  - `/verify_payment` - confirm payment after checkout

## Setup

1. Create a Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure environment variables in your shell or a `.env` loader.

Required variables:

- `BOT_TOKEN`
- `ADMIN_IDS` (comma-separated Telegram user IDs)
- `FLUTTERWAVE_SECRET_KEY`
- `PAYSTACK_SECRET_KEY`
- `PAYMENT_CALLBACK_URL` (optional for webhook-based verification)

3. Run the bot:

```powershell
python main.py
```

## Notes

- The bot uses SQLite locally for storage.
- Payment verification uses API calls; deploy the bot to a hosted environment to support callback-based workflows.
- Make sure your admin Telegram IDs are correct so you can manage levels and predictions.
