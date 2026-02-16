# Database Migrations with Alembic

This guide explains how to use Alembic for managing database schema migrations in the trading bot.

## Why Alembic?

We use Alembic for:
- ✅ **Version Control** - Track every schema change
- ✅ **Automatic Tracking** - Database knows which migrations are applied
- ✅ **Reproducibility** - Apply same migrations everywhere (dev, test, prod)
- ✅ **Rollback Capability** - Downgrade to previous schema if needed
- ✅ **Raw SQL Support** - Works perfectly with our psycopg3 + raw SQL approach
- ✅ **No ORM Required** - Zero dependency on SQLAlchemy

## Project Structure

```
trading-bot/
├── alembic/
│   ├── env.py                 # Alembic environment config
│   ├── alembic.ini            # Alembic settings
│   ├── script.py.mako         # Migration template
│   ├── versions/              # Migration files
│   │   ├── 001_initial_schema.py
│   │   ├── 002_add_new_table.py
│   │   └── ...
│   └── __init__.py
├── src/database/
│   ├── init.py                # Now uses Alembic
│   ├── repository.py
│   └── health.py
└── requirements.txt           # Contains: alembic>=1.12.0
```

## Initial Setup

### 1. Install Alembic

```bash
pip install -r requirements.txt
# Or just: pip install alembic>=1.12.0
```

### 2. Initialize Database

Run migrations to set up initial schema:

```bash
python -m src.database.init
```

Expected output:
```
INFO | ✅ Connecting to database: postgresql://...
INFO | Running database migrations...
INFO | Alembic version table created
INFO | Running upgrade → 001_initial_schema ... done
INFO | ✅ Database initialization complete!
INFO | ✅ All migrations applied successfully
```

## Common Tasks

### Create a New Migration

When you need to modify the schema (add column, new table, etc.):

```bash
alembic revision --message "add trading_events table"
```

This creates a new file: `alembic/versions/NNN_add_trading_events_table.py`

### Edit Migration File

```python
def upgrade():
    """Changes to apply"""
    op.execute("""
        ALTER TABLE trades
        ADD COLUMN max_loss NUMERIC(20, 8)
    """)

def downgrade():
    """Undo changes"""
    op.execute("""
        ALTER TABLE trades
        DROP COLUMN max_loss
    """)
```

### Apply Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply next migration
alembic upgrade +1

# Apply specific revision
alembic upgrade 002
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback all migrations
alembic downgrade base

# Rollback to specific revision
alembic downgrade 001
```

### Check Current Version

```bash
alembic current
# Output: 001 (migration 001_initial_schema is current)
```

### View History

```bash
alembic history
# Shows all migrations and which are applied
```

## Migration File Structure

### Example: Add Column

```python
"""Add max_loss column to trades.

Revision ID: 002
Revises: 001
Create Date: 2026-02-15 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new column
    op.execute("""
        ALTER TABLE trades
        ADD COLUMN max_loss NUMERIC(20, 8)
    """)


def downgrade() -> None:
    # Remove column on rollback
    op.execute("""
        ALTER TABLE trades
        DROP COLUMN max_loss
    """)
```

### Example: Create Table

```python
"""Create alert_logs table.

Revision ID: 003
Revises: 002
Create Date: 2026-02-15 16:00:00.000000

"""
from alembic import op

revision: str = '003'
down_revision: Union[str, None] = '002'

def upgrade() -> None:
    op.execute("""
        CREATE TABLE alert_logs (
            id SERIAL PRIMARY KEY,
            alert_type VARCHAR(50) NOT NULL,
            channel VARCHAR(50) NOT NULL,
            recipient VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT NOW()
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alert_logs")
```

## Workflow

### Development: Adding a Feature

1. **Identify schema change needed** (e.g., "add max_loss to trades")

2. **Create migration**:
   ```bash
   alembic revision --message "add max_loss to trades"
   ```

3. **Edit migration file**:
   ```python
   def upgrade():
       op.execute("ALTER TABLE trades ADD COLUMN max_loss NUMERIC(20, 8)")

   def downgrade():
       op.execute("ALTER TABLE trades DROP COLUMN max_loss")
   ```

4. **Apply migration**:
   ```bash
   alembic upgrade head
   ```

5. **Update your code** to use the new column

6. **Test locally**, then commit both:
   - Migration file
   - Code changes

### Production: Deploying

1. **Pull latest code** (includes new migration)
2. **Apply migrations**:
   ```bash
   alembic upgrade head
   ```
3. **Deploy application** (now uses new schema)
4. **Verify** tables/columns exist:
   ```sql
   SELECT * FROM information_schema.columns
   WHERE table_name = 'trades';
   ```

## Important Notes

### Naming Conventions

Migration files follow pattern: `NNN_description.py`
- `NNN` = Revision number (001, 002, 003, etc.)
- `description` = What changed (add_column, create_table, etc.)

**Good names:**
- `001_initial_schema.py`
- `002_add_trades_table.py`
- `003_add_max_loss_column.py`

**Bad names:**
- `001_migration.py` (too vague)
- `add_stuff.py` (no version)

### Reversible Migrations

Always provide both `upgrade()` and `downgrade()`:

```python
def upgrade():
    op.execute("...")  # Forward

def downgrade():
    op.execute("...")  # Backward
```

### Never Edit Applied Migrations

❌ **Don't do this:**
```python
# DON'T edit 001_initial_schema.py if it's already applied
# Alembic won't re-run it
```

✅ **Do this instead:**
```python
# Create a new migration for the change
alembic revision --message "add new column"
```

### Testing Migrations

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade base

# Test upgrade again
alembic upgrade head
```

## Common Patterns

### Add Column with Default

```python
op.execute("""
    ALTER TABLE trades
    ADD COLUMN profit_margin FLOAT DEFAULT 0.0
""")
```

### Add Index

```python
op.execute("""
    CREATE INDEX idx_trades_profit
    ON trades(pnl_percent DESC)
""")
```

### Rename Column

```python
op.execute("""
    ALTER TABLE trades
    RENAME COLUMN pnl_percent TO return_percent
""")
```

### Change Data Type

```python
op.execute("""
    ALTER TABLE trades
    ALTER COLUMN entry_price TYPE NUMERIC(25, 10)
""")
```

## Troubleshooting

### "No such revision as '001'"

**Problem:** Migration file doesn't exist

**Solution:**
```bash
# Check migration files
ls alembic/versions/

# Check migration status
alembic current
alembic history
```

### "alembic.util.exc.CommandError: Can't find identifier in the source text"

**Problem:** Alembic config not found

**Solution:**
```bash
# Verify alembic.ini exists
ls alembic/alembic.ini

# Verify DATABASE_URL is set
echo $DATABASE_URL
```

### Database already has tables (after initial migration)

**Solution:**
```bash
# Initialize migration history without running migrations
alembic stamp head
```

### Need to rollback in production

**Careful approach:**
```bash
# Check what will be downgraded
alembic downgrade --dry-run -1

# Actually downgrade
alembic downgrade -1

# Verify
alembic current
```

## Next Steps

### For You (User)

1. ✅ Alembic is set up
2. ✅ Initial migration exists
3. ✅ Database initialized with `python -m src.database.init`
4. Next: Run the bot and it will use the migrated schema

### Adding Features Later

When you need schema changes:
1. Create migration: `alembic revision --message "description"`
2. Edit migration file
3. Apply: `alembic upgrade head`
4. Update code

### For Week 2

When adding alerts, you might need:
```bash
alembic revision --message "create alert_logs table"
# Then edit and apply
```

## Reference

| Command | Purpose |
|---------|---------|
| `alembic revision -m "msg"` | Create new migration |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Rollback one migration |
| `alembic current` | Show current version |
| `alembic history` | Show all migrations |
| `alembic stamp head` | Mark DB as current without running |

## Related Files

- **alembic/env.py** - Configuration for psycopg3
- **alembic/alembic.ini** - Alembic settings
- **alembic/versions/** - All migration files
- **src/database/init.py** - Initialization script
- **alembic/script.py.mako** - Template for new migrations

---

**Ready to use!** Alembic is now integrated and ready for future schema changes. 🎯
