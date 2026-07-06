-- 0007_internal_note_message_timestamp.sql — fix a real gap in 0005:
-- internal_note had no column for the ORIGINAL message/note timestamp
-- (when a Slack message was actually sent, or a CSM note actually
-- written). The ingest path was writing only created_at (when the row
-- was inserted into Postgres), silently conflating ingestion time with
-- event time -- every backfilled or late-ingested note would carry the
-- wrong timestamp. Migrations are immutable once applied (0005's own
-- header), so this is an additive ALTER, not an edit to 0005.
--
-- Nullable: existing rows (if any) predate this column and have no
-- source-of-truth event time to backfill from; NULL is honest, a
-- fabricated created_at-as-message_ts is not.

ALTER TABLE internal_note ADD COLUMN message_ts timestamptz;
