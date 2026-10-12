# Browser interaction

Read before browser work on either day. Follow the dedicated-profile requirements, current workflow phase, and existing action limits.

Use visible site controls for ordinary shopping. Choose actions because they help inspect a product or complete the current step. Do not add random delays, mouse movements, typing mistakes, or unnecessary scrolling.

## Observe, act, verify

- Choose each target from a current browser observation.
- If the target is outside the visible viewport, scroll to reveal it and observe again before clicking.
- After navigation or a meaningful page change, obtain a fresh observation. Do not reuse stale element references or coordinates.
- Wait for evidence of readiness: loaded results, a visible product title, an enabled control, or a confirmed action result.
- If an action has an uncertain outcome, inspect the page before retrying.

## Search and text entry

- Search through Amazon's visible search field.
- Focus the field, replace an existing query when necessary, and enter an allowlisted product name using the tool's supported typing action.
- Submit with Enter or the visible search button.
- Do not substitute direct search URLs, clipboard paste, or instant field replacement when the supported typing action is available.
- Do not require character-by-character entry or artificial typing delays.
- If typing is unavailable, report the limitation before using a fallback.
- Passwords, API keys, and verification codes follow their separate secure-entry instructions.

## Product inspection and scrolling

- Review relevant visible search results before choosing a product.
- Open a product by clicking its observed result link.
- Inspect its title, selected variant, and relevant product details. Read specifications or reviews when they help assess the product.
- Scroll according to the content and viewport. Avoid arbitrary scroll counts, repeated movement, or opening sections solely to generate activity.
- Record only pages and details actually observed.

## Navigation

- Use browser Back to return to the results when continuing the same search. Reobserve the restored page and its scroll position.
- Use Amazon's visible controls to inspect the cart or change a search.
- Direct URL entry is appropriate for initial marketplace entry, profile verification, or recovery when ordinary navigation cannot resume the task.
- Explain a recovery shortcut briefly and verify the destination afterward.
- Preserve the cart-intent and confirmation procedure. Never repeat an uncertain cart action without checking its result.

## Browsing time

- Count time spent actively searching, inspecting results, and reviewing products within the authorized workflow.
- Pause the timer for blockers, user input, unrelated setup, or inactivity. Use `workflow.py browse-stop ACCOUNT_ID --result interrupted` when the Day 1 timer is running.
- Resume with `workflow.py browse-start ACCOUNT_ID` only after the blocker is resolved and the current page is verified.
- Do not fill the timer with idle waits or unnecessary interactions.

These instructions do not change workflow permissions, cart limits, credential handling, or account-verification requirements.
