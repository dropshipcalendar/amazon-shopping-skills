# One-time SMS

Use one-time SMS verification only when Amazon requests a phone during `signup`. No rental, renewal, automatic credit top-up, or number cycling. Preserve SMS opt-outs and the approved total spending/attempt limits.

## Readiness

During setup and before registration, list services and check the exact Amazon shopping service:

```text
PY SKILL/scripts/providers.py phone-services ACCOUNT_ID
PY SKILL/scripts/providers.py phone-check ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
```

Required balance is `max(sms_min_balance_usd, live quote)`, with a default floor of $0.75. Readiness also requires the quote to fit the remaining approved cap and allocation allowance. Balance is not spending authorization. Ask once for a missing cap or required funding, preserving progress; do not promise a deposit equal to the shortfall.

## Allocation and verification

```text
PY SKILL/scripts/providers.py phone-create ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
PY SKILL/scripts/providers.py phone-messages ACCOUNT_ID
PY SKILL/scripts/providers.py phone-cancel ACCOUNT_ID
```

Creation refreshes price/balance, reserves spending, and supplies the provider's maximum price. Reuse a saved allocation. Poll with bounded waits until its expiry, enter only the current code, and verify the Amazon result.

An uncertain purchase blocks another allocation: reconcile provider history and the saved ledger first. Cancellation does not establish a refund or restore the attempt allowance. Stop for another person's account, a rejected/exhausted verification, or an unsupported service. Retain number/expiry records; future access is not guaranteed. Do not change the user's marketplace to fit the provider's US numbers.

API references:
- Authentication: https://landing.textverified.com/automate
- REST API: https://www.textverified.com/docs/api/v2
- Balance: https://textverified-python.readthedocs.io/en/latest/_modules/textverified/account_api.html
- Pricing and maximum price: https://textverified-python.readthedocs.io/en/latest/api_reference.html
