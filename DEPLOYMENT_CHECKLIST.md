# Deployment Checklist

Complete checklist for deploying trading bot from development → paper trading → live trading.

## Pre-Deployment (Before Any Trading)

### Infrastructure

- [ ] Docker Desktop installed and running
- [ ] Docker Compose version >=1.29
- [ ] 2GB free disk space for database
- [ ] Stable internet connection
- [ ] Firewall allows outbound connections (trading APIs)

### Credentials & Access

- [ ] Alpaca account created
- [ ] Alpaca API keys (paper trading)
- [ ] Telegram account active
- [ ] Telegram bot created (@BotFather)
- [ ] Telegram chat ID obtained
- [ ] All credentials stored securely (not in git)

### Code & Configuration

- [ ] Trading bot source code cloned/downloaded
- [ ] `.env.example` copied to `.env`
- [ ] All required fields in `.env` filled with valid values
- [ ] `TRADING_ENV=paper` set for testing
- [ ] `BROKER=alpaca` set initially
- [ ] No default passwords in `.env`
- [ ] `.env` added to `.gitignore`

### Initial Run

- [ ] `docker-compose up -d` completes successfully
- [ ] Both `postgres` and `trading-bot` containers running
- [ ] Telegram bot receives startup message
- [ ] `/status` command works in Telegram
- [ ] Logs show no errors: `docker logs trading-bot | grep ERROR`
- [ ] Database connected: `SELECT 1 FROM health_checks` works

---

## Paper Trading Phase (Recommended: 2-4 weeks)

### Observation (Week 1)

- [ ] Bot runs continuously during market hours (9:30 AM - 4:00 PM ET)
- [ ] Telegram alerts received for each trade
- [ ] Trade records appear in database
- [ ] `/trades` command shows trades in Telegram
- [ ] No critical errors in logs
- [ ] Memory usage stable (check `docker stats`)

### Validation (Week 2-3)

- [ ] At least 50+ trades executed
- [ ] Win rate calculated: `/metrics`
- [ ] Win rate >50% (profitable)
- [ ] Profit factor >1.5 (good performance)
- [ ] No unexpected errors or crashes
- [ ] Positions open and close as expected
- [ ] Database queries run without issues

### Performance Review (Week 3+)

- [ ] Review `/metrics` daily
- [ ] Win rate is consistent (not volatile)
- [ ] No losses in excess of risk limit
- [ ] Strategy logic appears sound
- [ ] Portfolio hasn't had major drawdown
- [ ] Health checks all showing GREEN (🟢)

### Decision Point: Live Trading?

**Only proceed if ALL of these are true:**

- [ ] Win rate >50%
- [ ] Profit factor >1.5
- [ ] Ran for 2+ weeks without crashes
- [ ] Comfortable with risk level
- [ ] Understand potential for losses
- [ ] Have emergency contact procedure with father

---

## Pre-Live Trading Setup

### Live API Keys

- [ ] Alpaca live account verified (if needed)
- [ ] Alpaca live API keys obtained (different from paper)
- [ ] Saved securely (not in git)
- [ ] Not shared publicly

### Testing Live Keys (Without Trading)

```bash
# Create .env.live (separate config)
cp .env .env.live
# Edit .env.live with live credentials

# Test connection only
docker exec trading-bot python -c \
  "from config.settings import load_settings; s = load_settings(); print(f'Broker: {s.broker}')"
```

- [ ] Live API key validates successfully
- [ ] Can read account information
- [ ] Can see live portfolio value
- [ ] No errors connecting

### Position Size Reduction

- [ ] `MAX_POSITION_SIZE=0.01` (1% instead of 10%)
- [ ] `MAX_PORTFOLIO_RISK=0.001` (0.1% instead of 2%)
- [ ] Strategy parameters reviewed
- [ ] Risk settings properly configured

### Father's Notification Setup

- [ ] Father has Telegram installed
- [ ] Bot is added to father's Telegram
- [ ] Father tested `/status` command
- [ ] Father can see trade alerts
- [ ] Emergency procedure documented

---

## Live Trading Phase (Week 1 - Critical Monitoring)

### First Day

- [ ] Switch `TRADING_ENV=live` in `.env`
- [ ] Restarted bot: `docker-compose restart trading-bot`
- [ ] Checked logs: `docker logs trading-bot | grep -i live`
- [ ] First trade verified (check `/trades` in Telegram)
- [ ] Trade executed successfully
- [ ] Position monitoring works
- [ ] No API errors

### First Week

- [ ] Daily review of `/metrics`
- [ ] Daily review of `/trades`
- [ ] Father receiving alerts
- [ ] No unexpected behavior
- [ ] Win rate similar to paper trading
- [ ] Position sizing appropriate
- [ ] Losses within expected range (if any)

### End of Week 1 Decision

**Continue if:**
- [ ] All trades executed correctly
- [ ] Performance similar to paper trading
- [ ] No technical issues
- [ ] Risk management working

**Pause if:**
- [ ] Performance worse than paper trading
- [ ] Unexpected trades or errors
- [ ] Risk management not working
- [ ] Father asks to pause

---

## Ongoing Operations (Week 2+)

### Daily Tasks

- [ ] Check Telegram alerts (trades received)
- [ ] Monitor `/metrics` for win rate
- [ ] Check logs for errors: `docker logs trading-bot | grep -i error`
- [ ] Verify portfolio health

### Weekly Tasks

- [ ] Review full trade history
- [ ] Check database performance: `docker stats`
- [ ] Backup database:
  ```bash
  docker exec trading-bot-db pg_dump -U postgres -d trading_bot > backup_$(date +%Y%m%d).sql
  ```
- [ ] Review father's feedback

### Monthly Tasks

- [ ] Archive old trades (>6 months):
  ```sql
  CREATE TABLE trades_archive AS
  SELECT * FROM trades WHERE entry_timestamp < NOW() - INTERVAL '6 months';
  ```
- [ ] Performance analysis
- [ ] Strategy parameter review
- [ ] Decide: continue as-is or optimize

### Emergency Procedures

**If Portfolio Losing Money:**
- [ ] `/pause` bot immediately
- [ ] Review recent trades
- [ ] Check market conditions
- [ ] Decide: resume or adjust strategy

**If Bot Crashes:**
- [ ] Check logs: `docker logs trading-bot`
- [ ] Check database: `docker logs postgres`
- [ ] Restart: `docker-compose restart`
- [ ] Verify all positions closed safely

**If Database Issues:**
- [ ] Stop bot: `docker-compose down`
- [ ] Restore from backup: `psql < backup.sql`
- [ ] Restart: `docker-compose up -d`
- [ ] Verify data integrity

**If Telegram Not Working:**
- [ ] Check token in `.env`
- [ ] Check chat ID
- [ ] Restart bot: `docker-compose restart trading-bot`
- [ ] Test: `/help` in Telegram

---

## Operational Maintenance

### Resource Monitoring

```bash
# Check CPU/Memory
docker stats

# Should see:
# trading-bot: <50% CPU, ~200-300MB memory
# postgres: <30% CPU, ~100-200MB memory
```

- [ ] CPU usage normal (<80%)
- [ ] Memory usage stable (no leaks)
- [ ] Disk space sufficient (>1GB free)

### Database Health

```bash
# Check database size
docker exec trading-bot-db psql -U postgres -d trading_bot \
  -c "SELECT pg_size_pretty(pg_database_size('trading_bot'))"
```

- [ ] Database size <1GB
- [ ] Query performance good
- [ ] Backups running successfully
- [ ] No corruption detected

### Alerts & Notifications

- [ ] Telegram bot responding to commands
- [ ] Trade alerts being sent
- [ ] Error alerts being sent
- [ ] Father receiving notifications

### Log Management

```bash
# Logs are automatically rotated (10MB max per file, 3 files)
docker-compose logs --tail=100 trading-bot
```

- [ ] Logs are clean (no spam)
- [ ] Error logs reviewed regularly
- [ ] Old logs archived or deleted
- [ ] No sensitive data in logs

---

## Upgrade Procedure (When Updating Code)

1. [ ] Stop bot: `docker-compose down`
2. [ ] Backup database: `pg_dump > backup.sql`
3. [ ] Update code: `git pull` or download new version
4. [ ] Review changes: `git diff`
5. [ ] Rebuild image: `docker-compose build`
6. [ ] Start bot: `docker-compose up -d`
7. [ ] Run migrations: `docker exec trading-bot alembic upgrade head`
8. [ ] Verify: `docker logs trading-bot | head -20`
9. [ ] Test in Telegram: `/status`

---

## Scaling Up (Higher Position Sizes)

**Only increase position size if:**
- [ ] Win rate >60% consistently
- [ ] Profit factor >2.0
- [ ] At least 3 months of live trading
- [ ] No significant losses
- [ ] Father agrees

**Process:**
1. [ ] Backup current `.env`
2. [ ] Increase `MAX_POSITION_SIZE` by 25% only
3. [ ] Test for 1 week
4. [ ] Review results
5. [ ] If good, repeat or stop
6. [ ] Never exceed 0.5 (50% of portfolio per trade)

---

## Shutdown Procedure

### Planned Shutdown

```bash
docker-compose down
```

- [ ] Bot receives shutdown signal
- [ ] All open positions noted
- [ ] Final health checks saved
- [ ] Database safely closed
- [ ] All data persisted

### Emergency Shutdown

```bash
docker-compose down -v  # ⚠️ This deletes database!
```

Only use if database is corrupted. Restore from backup afterward.

### Data Preservation

```bash
# Always backup before shutdown
docker exec trading-bot-db pg_dump -U postgres -d trading_bot > final_backup.sql
```

- [ ] Final backup created
- [ ] Backup tested (can restore)
- [ ] Trade history preserved
- [ ] Ready to restart

---

## Sign-Off

### Developer Sign-Off

- [ ] Code reviewed and tested
- [ ] No known bugs or issues
- [ ] Documentation complete
- [ ] Ready for paper trading

**Developer:** _________________ **Date:** _______

### Father's Sign-Off

- [ ] Understands risks involved
- [ ] Can use Telegram to monitor
- [ ] Comfortable with position sizes
- [ ] Ready to proceed

**User (Father):** _________________ **Date:** _______

---

## Reference

### Key Commands

| Task | Command |
|------|---------|
| Start | `docker-compose -f docker/docker-compose.yml up -d` |
| Stop | `docker-compose -f docker/docker-compose.yml down` |
| Logs | `docker-compose -f docker/docker-compose.yml logs -f` |
| Status | `docker-compose -f docker/docker-compose.yml ps` |
| Backup | `docker exec trading-bot-db pg_dump -U postgres -d trading_bot > backup.sql` |
| Restart | `docker-compose -f docker/docker-compose.yml restart` |

### Contact & Support

- **Logs Location:** Printed to console, also in `logs/`
- **Database Access:** `psql postgresql://postgres:postgres@localhost:5432/trading_bot`
- **Telegram Support:** Check `docs/TELEGRAM_SETUP.md`
- **Documentation:** See project `docs/` folder

---

**This checklist ensures safe, gradual progression from development to live trading.**

Complete each section before proceeding. When in doubt, wait another week. 🚀
