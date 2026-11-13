Earnly V8 payment-integration candidate — NOT deployed.

Changes:
- Removes missing v7 asset references to avoid 404s.
- Keeps approved-only empty catalog (no unverified listings published).
- Reuses existing Telegram Stars invoice endpoint for Premium (500 Stars).
- Provides inline checkout feedback, guards repeat clicks, and refreshes server-verified membership after Telegram reports payment.
- Does not enable public Premium/VIP purchase buttons or VIP checkout.
- Does not modify Supabase functions, Telegram webhook, or payment database.

To deploy: inspect files, replace site files in your GitHub Pages repository, then test inside Telegram. Do not enable public purchases before a real payment, webhook and membership test succeeds.

Known limits: No live Telegram/Supabase end-to-end test was run; membership may update asynchronously, so a delayed refresh might be needed. Discovery remains paused.
