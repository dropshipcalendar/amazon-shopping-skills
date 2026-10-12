# TextVerified phone branch

Load only when Amazon requests a phone number during `signup`. The user has selected **one-time SMS verification only**. Use `sms_mode=verification` and TextVerified's verification API. Never use rentals, reservations, renewals, or a rental fallback. SMS is enabled by default (`sms_enabled: true`), but allocation requires `TEXTVERIFIED_API_KEY` and `TEXTVERIFIED_API_USERNAME` from native storage or approved environment injection, plus a positive user-approved `sms_max_total_usd`. Accept that limit once in private setup; do not ask again for the same authorized allocation within it. A null limit is pending, not unlimited. Honor a saved disabled toggle. Do not purchase credit or infer a budget.

One-time numbers can become unavailable after completion; retain the allocation and expiry record without promising future access. Do not reopen the number-type choice or recommend a rental during this workflow. The API supports US numbers; do not change the user's stated marketplace or location to fit a number.

## One-time verification helper

```text
PY SKILL/scripts/providers.py phone-services ACCOUNT_ID
PY SKILL/scripts/providers.py phone-quote ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
PY SKILL/scripts/providers.py phone-create ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
PY SKILL/scripts/providers.py phone-messages ACCOUNT_ID
PY SKILL/scripts/providers.py phone-cancel ACCOUNT_ID
```

Select the exact Amazon shopping service returned by the live list, not a guessed ID or another Amazon product. The helper requires `sms_mode=verification`, fetches a live quote, enforces the configured cumulative cap and allocation count, reserves the cost before purchasing, and supplies `max_price` to the provider. It never automatically retries a purchase. Run messages repeatedly with short bounded waits, respecting the returned expiration. Enter only the fresh code for this number and current request, then observe the Amazon page before declaring success.

If create times out, the saved allocation stays `uncertain` and blocks further purchases. Reconcile through TextVerified's account history before editing the state with the actual provider ID and result. Do not clear the spending reservation based on a missing response. If a returned number is already associated with another person's account, stop without reading or accessing that account.

On a number rejection or expired request, stop within the configured attempt limit. Cancellation does not prove a refund, restore an allocation allowance, or ensure future access. The helper conservatively retains reserved spending and counts all attempted allocations. Never cycle numbers to get around a website restriction.

If one-time verification is unavailable, rejected, or exhausted, report the blocker. Do not switch to a rental, enable renewal, or change the configured number type.

Sources checked 2026-10-12:
- https://landing.textverified.com/automate
- https://www.textverified.com/faq
- https://textverified-python.readthedocs.io/en/latest/quickstart.html
- https://textverified-python.readthedocs.io/en/latest/
