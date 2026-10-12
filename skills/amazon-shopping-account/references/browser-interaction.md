# Browser interaction

Use current page observations and supported browser controls to perform the requested step. Choose actions that help inspect products or complete the workflow.

- Select targets from the current page. Reveal offscreen controls and observe again; refresh observations after navigation or meaningful page changes.
- Wait for evidence of readiness, such as loaded results or an enabled control. Inspect uncertain outcomes before retrying.
- Search through Amazon's visible search field and open observed result links. Prefer the tool's supported typing action; if unavailable, use a suitable supported text-entry method without interrupting the user.
- Inspect the title, variant, and relevant product details. Scroll as needed; read specifications or reviews when useful.
- Use Back or visible site controls to continue browsing. Direct navigation is appropriate for initial entry or recovery; verify the destination.
- Do not add random delays, typing mistakes, mouse movements, or unnecessary scrolling.
- Count active product exploration only. Pause the timer with `workflow.py browse-stop ACCOUNT_ID --result interrupted` for user input, unrelated setup, blockers, or inactivity; resume with `browse-start` once ready.
- Follow [credential handling](credentials.md) for secrets and the Day 1 cart-intent procedure for additions.

Report a browser blocker only after available supported methods cannot complete the step.
