# Day 1: signed-out product browsing

Complete initial setup, verify the dedicated profile, and confirm Amazon is signed out. Use the saved product allowlist and [browser interaction](browser-interaction.md) procedure.

1. Run `workflow.py browse-start ACCOUNT_ID`. It records Day 1's start date and timer. Do not register or obtain a phone number.
2. Search a subset of allowed categories that fits the 300-second budget. Inspect relevant products and record each observed page with `workflow.py viewed ACCOUNT_ID --product ALLOWLIST_NAME --url OBSERVED_HTTPS_URL`.
3. Check the guest cart before adding. Record `workflow.py cart-intent ACCOUNT_ID --product ALLOWLIST_NAME --url OBSERVED_PRODUCT_URL`, perform the addition once with quantity one, verify it, then record `cart-confirm ACCOUNT_ID --action-id RETURNED_ID`. Add at most two distinct matching products and preserve preexisting items.
4. Reconcile unconfirmed intents against the live cart. Use `cart-not-added` only when absence is established. Skip ambiguous products or actions requiring sign-in.
5. Check remaining active time with `status`. At completion run `browse-stop --result completed`; this records the actual completion time and sets Day 2's eligible date to the following local day. Use `--result interrupted` when pausing. Do not count idle time or mark completion from the timer alone.

After a crash with an active timer, use `browse-recover --observed-seconds N` for evidenced browsing only; use zero if unknown. Inspect existing cart intents before proceeding.

Follow [scheduling](scheduling.md) to remove the finished Day 1 task and confirm Day 2's task before ending this run. If unavailable, give a dated manual resume instruction. Preserve the guest cart; transfer through registration is not guaranteed.
