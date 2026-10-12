# Prepare once, configure privately

Use this flow for an installation/setup request. Preparation does not authorize browsing, account creation, inbox creation, SMS allocation, or scheduling. If the user's request also authorizes Day 1, prepare first and then follow the normal Day 1 gates. Day 2 credentials do not block Day 1.

## Prepare without a chat questionnaire

1. Follow `platform.md` and install the pinned requirements in the private runtime. Check the actual browser/control capabilities.
2. Run `PY SKILL/scripts/setup.py prepare shopping-01`. Use the stable default ID unless the user supplied another one. New accounts use Amazon.com and the locally detected IANA timezone. Pass `--marketplace` or `--timezone` only for a known user preference. Do not infer locale from a folder name. If timezone detection fails, obtain just the missing timezone.
3. Existing accounts retain settings, progress, limits, and credentials. Preparation never creates a replacement account to evade a blocked run. The returned account and launcher paths are authoritative.
4. Reopen and verify the dedicated Chrome profile using `browser-profile.md`, including available native computer controls if browser integration cannot attach. Confirm browser control and Amazon signed out before claiming Day 1 is ready. `profile_observed` is historical evidence; `day_one_readiness: requires_live_browser_check` deliberately does not certify the current browser. Complete this check independently of credential setup.
5. Run `PY SKILL/scripts/setup.py launch shopping-01`. A `setup_server_ready` result includes `setup_url`: open that exact URL on the same computer in an available visible browser, then confirm the blank form is displayed before handing over. The separate `open-setup` launcher starts the same server and opens the user's default browser automatically. Tkinter is not needed. A running server alone is not proof that the form is visible. Do not claim readiness if the dedicated shopping browser check failed; an unavailable configuration form alone does not block Day 1.

The account ID is fixed once prepared. The Soft blue form displays only the three provider fields, Save, and Configure later, with the official Dropship Calendar logo. It retains marketplace, timezone, products, SMS settings, and saved allocation count. Advanced settings use `configure --prompt` or the validated account config. Do not require provider keys before completing browser checks.

## Private configuration handoff

The form masks API keys. Blank fields preserve existing credentials. Save updates the fields the user filled in, including replacing an existing value; it never reveals saved credentials. The Amazon password is never collected by this form: the user enters it directly on Amazon during Day 2.

Tell the user to enter credentials privately and save. Stop browser/computer observations, screenshots, DOM reads, and clipboard access before private entry begins; resume only after the user says they finished. Do not automate secret entry. The form saves supplied credentials to a supported native OS store and preserves account settings. It makes only local requests, never contacts providers, and does not create an inbox, phone allocation, shopping browser session, or schedule. Some native stores can ask the user to unlock or authorize access; let the user handle those prompts.

SMS is enabled by default in one-time verification mode. The default allocation limit is one. The minimal credential form does not configure or approve spending. A user supplies and accepts a total dollar limit separately through the interactive setup command or explicit instruction before the first required SMS allocation. A blank limit leaves spending pending, not unlimited. A positive saved limit is the spending authorization, including preexisting configurations. Do not prompt again for the same authorized purchase within the cap. Purchase only during signup if Amazon requires a phone, and stop above the cap or on an uncertain outcome. Preserve existing opt-outs and limits on rerun. After any allocation attempt, setup refuses changes to SMS enablement or budget.

Save records `setup_saved_at` without starting the account workflow. Save and Configure later both clear the form and stop its server; Configure later writes nothing. The tab can remain open with its result. Sessions expire after 15 minutes; reopen the launcher for a new session. If the page reports an unknown save outcome, inspect nonsecret setup status before retrying. A vault can fail partway through saving multiple fields; account settings are not written after that failure. Check presence before retrying; refill only fields the user intends to update. Do not promise an all-or-nothing vault transaction.

For an existing Windows installation updated from the earlier credential implementation, follow the [Windows migration instructions](credentials.md#windows-replacements-and-existing-installations) to apply local-machine persistence to all already-saved fields without retyping them. New form saves already use the hardened behavior.

## Unavailable form or native store

If the form cannot open, provide the fully resolved command:

```text
PY SKILL/scripts/setup.py configure shopping-01 --prompt
```

This must run in the user's interactive local terminal, not agent-captured stdin. Ordinary settings are visible; credential input is hidden. An unavailable/locked native store does not fall back to plaintext files. The user can configure later and use the existing provider hidden prompts on Day 2, or use approved environment injection. Continue the independent Day 1 browser checks even if the form cannot open. Do not install Tkinter, a desktop, unlock a keyring, weaken a container, or configure a new secret service automatically.

## Status and continuation

```text
PY SKILL/scripts/setup.py status shopping-01
PY SKILL/scripts/setup.py status shopping-01 --check-credentials
```

Normal status does not read the vault. The optional check reports `configured`, `missing`, `locked`, or `unavailable` plus the source; it can trigger an OS access prompt and must be used only outside private entry. No secret values are returned. `provider_connection: not_tested` means saving/presence did not validate provider access.

If the agent remains active, use `setup_saved_at` and nonsecret status to confirm the handoff. Saving the form does not itself resume an ended agent turn. Ask the user to reply "configured" when finished if a supported continuation is not active. Do not poll a secret-entry window or create a scheduler solely to wait for configuration.

## User-facing reply

Keep detailed readiness flags internal. Lead with "Day 1 ready" after successful live verification. If credentials are incomplete, add one sentence explaining that configuration can be completed in the private form before Day 2. If their status was not checked, say so rather than asserting they are incomplete or complete. Then show only the two-step roadmap and the next action. Mention a pending SMS limit alongside configuration only when it needs attention; do not turn the response into a six-line status checklist.

Example after successful live verification and a confirmed incomplete configuration:

> **Day 1 ready.** Credential configuration is incomplete; use the private setup window now or before Day 2.
>
> 1. **Day 1:** When you ask me to start, browse the supplied product list for five minutes and add up to two matching products. No account is created yet.
> 2. **Day 2:** On the next eligible day, resume in the same browser profile to register and verify the account. Enter the Amazon password yourself; one-time SMS is used only if required, within your accepted limit.
>
> Save your settings privately, then reply "configured", or say "start Day 1" to configure credentials later.

If Day 1 is already authorized, continue it instead of asking the user to authorize it again. If it completes, report completion and its actual eligible Day 2 date with the manual resume instruction when needed. Never invent a date before Day 1 establishes it. A failed dedicated-browser check blocks readiness; report the specific missing capability and which supported controls were tried. Missing credentials, an unavailable credential form, and a pending SMS spending limit do not block Day 1 readiness after successful browser verification.
