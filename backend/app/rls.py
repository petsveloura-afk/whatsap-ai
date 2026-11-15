"""Postgres Row-Level Security support (defence in depth). Policies are created by migration d3a4b5c6e7f8.
Enforcement needs BOTH: RLS_ENFORCE=1 and the app connecting as a NON-owner role (table owners bypass RLS unless FORCE'd) -
see docs/SECURITY.md. Default OFF => zero behaviour change. System/worker/admin/auth contexts run with bypass='on'."""
import contextvars, os
from sqlalchemy import event, text
current_uid: contextvars.ContextVar = contextvars.ContextVar("rls_uid", default=None)
ENFORCE = lambda: os.environ.get("RLS_ENFORCE") == "1"
USER_TABLES = ["search_configs", "listings", "telegram_connections", "refresh_tokens", "password_resets", "subscriptions", "payment_transactions",
               "user_preferences", "ai_memory", "user_profiles", "data_sources", "ingestion_events", "listing_deduplication",
               "user_listing_actions", "notification_preferences", "notifications", "api_keys", "webhook_endpoints",
               "webhook_deliveries", "referrals", "shared_links", "user_flags"]

def install(session_factory):
    @event.listens_for(session_factory, "after_begin")
    def _set(session, transaction, connection):
        if not ENFORCE() or connection.dialect.name != "postgresql": return
        uid = current_uid.get()
        connection.execute(text("SELECT set_config('app.user_id', :u, true), set_config('app.bypass_rls', :b, true)"),
                           {"u": uid or "", "b": "off" if uid else "on"})

def policy_sql(table: str) -> list[str]:
    col = "id" if table == "users" else "user_id"
    return [f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY", f"DROP POLICY IF EXISTS user_isolation ON {table}",
            f"CREATE POLICY user_isolation ON {table} USING ({col} = current_setting('app.user_id', true) OR current_setting('app.bypass_rls', true) = 'on') "
            f"WITH CHECK ({col} = current_setting('app.user_id', true) OR current_setting('app.bypass_rls', true) = 'on')"]
