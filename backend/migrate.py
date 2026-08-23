from pathlib import Path

from sqlalchemy import text

from app import app, db


MIGRATIONS_DIRECTORY = Path(__file__).parent / "migrations"


def split_statements(sql):
    return [
        statement.strip()
        for statement in sql.split(";")
        if statement.strip()
    ]


def run_migrations():
    migration_files = sorted(MIGRATIONS_DIRECTORY.glob("*.sql"))

    if not migration_files:
        raise RuntimeError(
            f"No SQL migrations found in {MIGRATIONS_DIRECTORY}"
        )

    with app.app_context():
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                      version VARCHAR(255) PRIMARY KEY,
                      applied_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

            for migration_file in migration_files:
                already_applied = connection.execute(
                    text(
                        """
                        SELECT 1
                        FROM schema_migrations
                        WHERE version = :version
                        """
                    ),
                    {"version": migration_file.name},
                ).scalar()

                if already_applied:
                    print(
                        f"Skipping previously applied migration: "
                        f"{migration_file.name}"
                    )
                    continue

                migration_sql = migration_file.read_text(
                    encoding="utf-8"
                )

                for statement in split_statements(migration_sql):
                    connection.execute(text(statement))

                connection.execute(
                    text(
                        """
                        INSERT INTO schema_migrations (version)
                        VALUES (:version)
                        """
                    ),
                    {"version": migration_file.name},
                )

                print(f"Applied migration: {migration_file.name}")


if __name__ == "__main__":
    run_migrations()