# Database Schema

## Core Tables

```
users
  id, username, password_hash, role (root|admin|user), is_active

broker_credentials
  id, user_id (FK), broker_type, environment,
  encrypted_api_key, encrypted_secret_key, encrypted_passphrase, label

trades
  id, user_id (FK), symbol, strategy, broker, bot_name,
  entry_price, entry_quantity, entry_order_id, entry_time,
  exit_price, exit_quantity, exit_order_id, exit_time,
  pnl, status

bot_sessions
  id, bot_name, user_id (FK), started_at, stopped_at, session_id

events
  id, event_type, symbol, strategy, broker, bot_name, details (JSONB), timestamp

health_checks
  id, broker, strategy, bot_name, last_check, status
```

## Multi-Tenancy Model

Every table with user data has a `user_id` foreign key. This is **row-level tenancy** — all users share one database, isolated by `WHERE user_id = ?` in every query.

Trade-offs:
- Simple to operate (one database to backup, migrate, monitor)
- Queries MUST always filter by user_id (a missed filter = data leak)
- Works up to ~100s of users. Beyond that, consider schema-per-tenant

## Credential Encryption

Broker API keys are encrypted at rest using **Fernet** (symmetric, authenticated encryption). The FERNET_KEY lives in environment variables, never in the database. Decryption happens only when the engine needs to connect to a broker.

## Migrations

Alembic manages schema changes in `shared/alembic/`. Current chain:
```
001_initial_schema -> 002_add_bot_sessions -> 003_add_bot_name
  -> 004_add_users_and_auth -> 005_add_user_id_to_all_tables
```

## Deep Dive

- Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- SQLAlchemy async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Multi-tenancy patterns: https://www.citusdata.com/blog/2018/06/28/multi-tenant-saas-database-schema/
