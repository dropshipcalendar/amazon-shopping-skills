# TextVerified phone branch

Connection, balance, and quote checks also run during [initial setup](setup.md) and before Day 2 registration. Allocation and message operations run only when Amazon requests a phone number during `signup`. The user has selected **one-time SMS verification only**. Use `sms_mode=verification` and TextVerified's verification API. Never use rentals, reservations, renewals, or a rental fallback. Requires the saved TextVerified connection or matching injected credentials, and an approved `sms_max_total_usd`. Do not purchase credit or infer a budget.

One-time numbers can become unavailable after completion; retain the allocation and expiry record without promising future access. Do not reopen the number-type choice or recommend a rental during this workflow. The API supports US numbers; do not change the user's stated marketplace or location to fit a number.

## One-time verification helper

```text
PY SKILL/scripts/providers.py phone-services ACCOUNT_ID
PY SKILL/scripts/providers.py phone-quote ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
PY SKILL/scripts/providers.py phone-check ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
PY SKILL/scripts/providers.py phone-create ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
PY SKILL/scripts/providers.py phone-messages ACCOUNT_ID
PY SKILL/scripts/providers.py phone-cancel ACCOUNT_ID
```

Select the exact Amazon shopping service returned by the live list, not a guessed ID or another Amazon product. The helper requires `sms_mode=verification`, refreshes live price and balance, requires at least `max(sms_min_balance_usd, quote)`, enforces the configured cumulative cap and allocation count, reserves the cost before purchasing, and supplies `max_price` to the provider. It never automatically retries a purchase. Run messages repeatedly with short bounded waits, respecting the returned expiration. Enter only the fresh code for this number and current request, then observe the Amazon page before declaring success.

If create times out, the saved allocation stays `uncertain` and blocks further purchases. Reconcile through TextVerified's account history before editing the state with the actual provider ID and result. Do not clear the spending reservation based on a missing response. If a returned number is already associated with another person's account, stop without reading or accessing that account.

On a number rejection or expired request, stop within the configured attempt limit. Cancellation does not prove a refund, restore an allocation allowance, or ensure future access. The helper conservatively retains reserved spending and counts all attempted allocations. Never cycle numbers to get around a website restriction.

If one-time verification is unavailable, rejected, or exhausted, report the blocker. Do not switch to a rental, enable renewal, or change the configured number type.

Sources checked 2026-10-12:
- https://landing.textverified.com/automate
- https://www.textverified.com/faq
- https://textverified-python.readthedocs.io/en/latest/quickstart.html
- https://textverified-python.readthedocs.io/en/latest/

## API references

- Authentication and API reference entry point: https://landing.textverified.com/automate
- REST API reference: https://www.textverified.com/docs/api/v2 (may redirect to the authenticated application).
- Account/balance read: https://textverified-python.readthedocs.io/en/latest/_modules/textverified/account_api.html (`GET /api/pub/v2/account/me`, SDK `client.account.balance`).
- Live quote and maximum price: https://textverified-python.readthedocs.io/en/latest/api_reference.html (`client.verifications.pricing`, `max_price`).

Consult these focused references when an API response differs; never dump account credentials or raw provider errors while troubleshooting.
