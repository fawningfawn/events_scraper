# TODO

## Database migrations

- Drop the `keyword` column from the `event_subscriptions` table.
  The column is dead: matching only uses `title_keyword`/`body_keyword`,
  and the ORM model no longer references it. Existing installs still have
  the column in their SQLite DB (harmless — ORM inserts just don't set it).
  When a migration system is ready, add a migration to `ALTER TABLE
  event_subscriptions DROP COLUMN keyword`.
