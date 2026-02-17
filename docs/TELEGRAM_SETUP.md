# Telegram Bot Setup Guide

Get real-time trading notifications and control your trading bot via Telegram.

## Overview

The Telegram bot provides:
- 📊 **Real-time trade alerts** - Instant notification when orders execute
- 📈 **Performance metrics** - Win rate, profit factor, Sharpe ratio
- 📝 **Recent trades** - View last trades with details
- ⚙️ **Bot control** - Pause/resume trading from your phone
- 🚨 **Error alerts** - Connection issues, critical errors
- 💚 **Health status** - Bot connection health monitoring

## Prerequisites

- Telegram app installed on your phone
- A Telegram account
- Access to BotFather (Telegram bot)

## Step 1: Create a Telegram Bot

### Via BotFather (Automated)

1. **Open Telegram** and search for `@BotFather`

2. **Start a conversation** with BotFather

3. **Type `/newbot`** and follow the prompts:
   ```
   BotFather: Alright, a new bot. How are we going to call it?
   You: Trading Bot

   BotFather: Good. Now let's choose a username for your bot...
   You: trading_bot_abc

   BotFather: Done! Congratulations on your new bot. Here are your bot's details:
   Name: Trading Bot
   @trading_bot_abc

   Use this token to access the Telegram Bot API:
   1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
   ```

4. **Copy the token** - You'll need this later

### Disable Public Bot (Optional but Recommended)

For privacy, make the bot private:
1. Type `/setprivacy` in BotFather
2. Select your bot
3. Choose "Disable" - only you can use it

## Step 2: Get Your Chat ID

### Option A: Using BotFather

1. In BotFather, type `/mybots`
2. Select your bot
3. Click "Inspect"
4. Look for your user ID in the response

### Option B: Using a Test Message

1. **Start a chat with your bot:**
   - Search for `@<your_bot_username>`
   - Click "START"

2. **Message any text to your bot**

3. **Visit this URL in your browser** (replace TOKEN):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

4. **Find your chat ID** in the response:
   ```json
   {
     "ok": true,
     "result": [
       {
         "update_id": 123456789,
         "message": {
           "message_id": 1,
           "chat": {
             "id": 987654321,  ← YOUR CHAT ID
             "first_name": "Your Name",
             ...
           }
         }
       }
     ]
   }
   ```

**Keep this ID safe!** You'll need it in the next step.

## Step 3: Configure Your Trading Bot

### Update .env File

```bash
# Edit or create .env
nano .env
```

Add these lines:

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
TELEGRAM_CHAT_ID=987654321
```

### Or Update config/config.yml

```yaml
app:
  telegram_token: "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
  telegram_chat_id: "987654321"
```

### Precedence

Environment variables override .env which override config.yml:

1. `TELEGRAM_TOKEN` environment variable (highest)
2. `.env` file
3. `config.yml`
4. Empty string (notifications disabled)

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs `python-telegram-bot>=21.0` which handles all Telegram communication.

## Step 5: Start Your Bot

```bash
python -m trading_bot.main
```

You should see:

```
INFO | Initializing Telegram bot...
INFO | ✅ Telegram bot initialized
INFO | Trading bot started successfully
```

And your bot will send a startup message on Telegram:

```
🤖 Trading Bot Started
Environment: PAPER
Broker: ALPACA
```

## Using the Telegram Bot

### Available Commands

Send these to your bot:

#### `/status` - Bot Status
```
Shows:
• Bot running status
• Current portfolio value
• Broker and environment
```

#### `/trades` - Recent Trades
```
Shows last 10 trades:
• Symbol
• Entry/Exit price
• P&L
• Strategy name
```

#### `/metrics` - Performance
```
Shows:
• Total trades
• Win rate (%)
• Profit factor
• Sharpe ratio
```

#### `/pause` - Pause Trading
```
Bot stops executing new trades
Current positions stay open
```

#### `/resume` - Resume Trading
```
Bot resumes executing trades
```

#### `/help` - Help
```
Shows all available commands
```

## Automatic Alerts

The bot sends automatic alerts for:

### Trade Execution
```
📈 Trade Executed

Symbol: BTC/USD
Side: BUY
Price: $50000.00
Quantity: 0.1000
Strategy: rsi_atr_trend
Time: 14:23:45 UTC
```

### Errors
```
🚨 Trading Bot Alert

Type: Connection Error
Message: WebSocket timeout
Time: 14:25:12 UTC
```

### Health Status
```
🟢 Health Check

Status: HEALTHY
Connection Errors: 0
Last Bar: 2026-02-15 14:30:00
Time: 14:35:00 UTC
```

### Bot Startup
```
🤖 Trading Bot Started

Environment: PAPER
Broker: ALPACA
```

### Bot Shutdown
```
🛑 Trading Bot Stopped

Shutdown time: 14:45:30 UTC
```

## Example Workflow

### Morning: Check Status
```
You: /status
Bot: 📊 Trading Bot Status
     Status: Running
     Portfolio Value: $25,450.32
     Broker: Alpaca (Paper)
```

### See Recent Trades
```
You: /trades
Bot: 📈 Recent Trades
     1. BTC/USD BUY @ $50000 | +$500 (+2.0%)
     2. SPY BUY @ $450 | -$150 (-1.5%)
     ...
```

### Check Performance
```
You: /metrics
Bot: 📊 Performance
     Total Trades: 42
     Win Rate: 57.14%
     Profit Factor: 1.83
```

### Pause Before Important Event
```
You: /pause
Bot: ⏸️ Trading Paused
     New trades will not execute
     Current positions remain open
```

### Resume Later
```
You: /resume
Bot: ▶️ Trading Resumed
     Bot will resume executing trades
```

## Troubleshooting

### "Bot not sending messages"

**Check if configured:**
```bash
echo $TELEGRAM_TOKEN
echo $TELEGRAM_CHAT_ID
```

Both should have values (not empty).

**Check bot is running:**
```bash
# In your terminal
tail -f /tmp/trading_bot.log | grep Telegram
```

Should show: `INFO | ✅ Telegram bot initialized`

### "Invalid token"

**Verify token format:**
- Format: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`
- From BotFather: `/mybots` → select bot → copy token

**Test token:**
```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

Should return bot info, not "Unauthorized".

### "Chat ID not found"

**Get chat ID again:**
1. Send any message to your bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Look for `"chat": {"id": YOUR_ID}`

### "Commands not showing"

The bot sets commands automatically on startup. If they don't appear:

1. **Restart the bot**
2. **Type `/` in Telegram** - should show command list after 30 seconds

### "Not receiving trade alerts"

**Check if trades are happening:**
```bash
grep -i "trade executed\|Signal executed" /tmp/trading_bot.log
```

If no trades are being executed, check strategy configuration instead.

**Check Telegram is enabled:**
```bash
grep -i telegram /tmp/trading_bot.log
```

## Security Notes

### Protect Your Token

⚠️ **Never commit these to git:**
```bash
# ❌ DON'T DO THIS
git add .env
git commit -m "Add telegram config"
```

✅ **Keep tokens secret:**
```bash
# Only in .env (add to .gitignore)
# Never share your token publicly
# Never paste in screenshots
```

### Regenerate Token if Compromised

If someone gets your token:

1. Go to BotFather
2. Type `/mybots` → select your bot
3. Click "API Token" → "Regenerate"
4. Update your `.env` file with new token

### Chat ID Privacy

Your chat ID is like a phone number - keep it private. Only the bot should have it.

## Multiple Bots

You can run multiple trading bots with different Telegram bots:

```bash
# Bot 1: Alpaca paper trading
TELEGRAM_TOKEN=token1 TELEGRAM_CHAT_ID=123 python -m trading_bot.main

# Bot 2: Coinbase live trading (different terminal)
TELEGRAM_TOKEN=token2 TELEGRAM_CHAT_ID=123 python -m trading_bot.main &
```

Each bot sends to its own Telegram bot, but same chat ID.

## Integration with Other Systems

### Forward to Multiple Chat IDs

To send alerts to multiple people:

1. Create a **Telegram Channel**
2. Add people to the channel
3. Use channel ID as `TELEGRAM_CHAT_ID`

### Telegram Groups

You can add your bot to a Telegram group:

1. Create a group chat
2. Add your bot to the group
3. Get the group ID
4. Use group ID as `TELEGRAM_CHAT_ID`

## Reference

| Component | File |
|-----------|------|
| **Bot Code** | `src/notifications/telegram_bot.py` |
| **Integration** | `src/main.py` (lines with `telegram_bot`) |
| **Config** | `config/settings.py` |
| **Env Template** | `.env.example` |

## FAQ

**Q: Can I use one bot for multiple trading strategies?**
A: Yes, one bot sends alerts for all strategies on the same chat.

**Q: What if the bot is offline?**
A: Telegram will queue messages for 24 hours. When bot comes back online, you'll get delayed alerts.

**Q: Can I control the bot from multiple devices?**
A: Yes, as long as they're in the same Telegram chat (personal account or group).

**Q: Does the bot need internet?**
A: Yes, it needs to connect to Telegram API to send messages.

**Q: Can I send custom commands?**
A: Not yet, but they're easy to add. See `src/notifications/telegram_bot.py` for examples.

## Next Steps

1. ✅ Set up Telegram bot token
2. ✅ Get your chat ID
3. ✅ Configure in `.env`
4. ✅ Start trading bot
5. Try commands: `/status`, `/trades`, `/metrics`
6. Test pause/resume: `/pause` then `/resume`

## Support

- **Can't find token?** Check BotFather `/mybots`
- **Chat ID issues?** Visit `getUpdates` URL directly
- **Bot not responding?** Check logs: `grep Telegram /tmp/trading_bot.log`
- **Tokens being rejected?** Regenerate in BotFather

---

**You're all set!** Your trading bot is now on Telegram. 📱

Notifications will appear as they happen, and your father can monitor the bot from his phone anytime. 🚀
