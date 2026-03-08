from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_prototype_migrations(engine: Engine) -> None:
    """Apply minimal additive migrations needed for prototype evolution."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "trend_runs" in tables:
        columns = {col["name"] for col in inspector.get_columns("trend_runs")}
        if "selector_config" not in columns:
            if engine.dialect.name == "postgresql":
                ddl = "ALTER TABLE trend_runs ADD COLUMN selector_config JSONB"
            else:
                ddl = "ALTER TABLE trend_runs ADD COLUMN selector_config JSON"
            with engine.begin() as conn:
                conn.execute(text(ddl))
