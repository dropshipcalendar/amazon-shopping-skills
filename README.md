# Amazon Shopping Account skill

Instructions and local helpers for a computer-using AI agent to set up one user-owned Amazon shopping account across two days. Day 1 browses the bundled product allowlist while signed out for five minutes and adds at most two matching products to the cart. Day 2 registers the account in the same dedicated Chrome profile, using AgentMail and, only if Amazon requests it, one-time TextVerified SMS. The workflow does not place orders.

No particular agent application, plugin marketplace, or skill loader is required. The agent needs access to the complete skill folder and the computer capabilities described below. This repository does not include an agent runtime or hosted signup service.

## Get the skill

Download this repository with GitHub's **Code -> Download ZIP**, then extract it, or clone it:

```sh
git clone https://github.com/dropshipcalendar/amazon-shopping-skills.git
```

Give your agent access to the extracted folder and have it read [skills/amazon-shopping-account/SKILL.md](skills/amazon-shopping-account/SKILL.md). Keep the whole folder together: the skill needs its scripts, references, and product allowlist. Reading only the raw SKILL.md from the web is not a complete installation.

### Optional skill-manager installation

If your agent has a compatible skill manager and Node.js with npm/npx is available:

```sh
npx skills add dropshipcalendar/amazon-shopping-skills --skill amazon-shopping-account --global
```

Select only the current agent's supported destination; do not install into every detected agent. If this agent has no supported destination, use the complete downloaded folder. Omit `--global` for a project-local installation; add `--copy` if symbolic links are unavailable. See the installer's [current requirements](https://github.com/vercel-labs/skills/blob/main/package.json) and [installation options](https://github.com/vercel-labs/skills#install-a-skill). The installer copies files; the instruction below also requests initial setup.

### Copy-and-paste setup instruction

> Install with `npx skills add dropshipcalendar/amazon-shopping-skills --skill amazon-shopping-account --global` for this agent. Read the installed skill's `SKILL.md` and run initial setup now, in this same turn. Keep replies brief and stop after setup; do not start Amazon browsing, registration, SMS purchases, or scheduling.

## Required computer capabilities

- Windows, macOS, or Linux with Python 3.11 or newer and a controllable, persistent Chrome profile (Chromium is also supported on Linux).
- Local file and terminal access, plus an available native credential store or approved secret injector.
- For registration, the user's name and secure password entry. Product names are bundled.

Follow [initial setup](skills/amazon-shopping-account/references/setup.md) for the private runtime and provider connections. Existing credentials are reused; first-time AgentMail signup and guided TextVerified login are part of setup. Keys never belong in chat, command arguments, repository files, or progress logs.

Setup checks SMS price and balance against the configured minimum and approved spending cap. The default balance floor is $0.75, not a fixed price guarantee; see [phone checks](skills/amazon-shopping-account/references/phone.md).

## How the two days continue

Progress lives in local state files, so the agent does not need to remember a previous conversation. See [continuation and scheduling](skills/amazon-shopping-account/references/scheduling.md).

- **Automatic:** If an available scheduler can resume the agent or invoke a verified agent runner with access to the same files, credentials, and browser profile, the agent records that task's ID and removes it after completion. A timer that only launches a page or runs a helper is insufficient.
- **Manual:** Without those capabilities, the agent saves Day 1 and provides a dated resume instruction. Give it to a compatible computer-using agent on or after the eligible date. A reminder is not automatic execution.

Follow the skill's entry rule: install-and-follow requests run initial setup in the same turn; the two-day workflow starts when requested. Keep the files, state, credentials, and browser profile available on the selected computer through Day 2. Verify the actual runner before promising unattended completion.

## Private runtime data

Account state and Chrome profiles live outside the skill folder at the paths returned by `workflow.py environment` and `workflow.py status`. Keys live in the native vault or approved secret injector. Do not publish these records or profiles.

Nonsecret setup checks live in account state; `.connections/agentmail-signup.json` records any one-shot onboarding intent. Preserve them across runs to avoid repeating uncertain actions.

## Repository layout

```text
amazon-shopping-skills/
├── README.md
├── .gitignore
└── skills/
    └── amazon-shopping-account/
        ├── SKILL.md
        ├── assets/
        ├── references/
        ├── scripts/
        └── tests/
```

## Maintenance and validation

With the requirements installed in a private Python environment, run:

```sh
python -m unittest discover -s skills/amazon-shopping-account/tests -v
```

Use that environment's interpreter path or `python3` where appropriate. Tests use temporary state and fake vaults, clipboards, providers, and schedulers. They never create live accounts or read actual stored credentials.

To check discovery without installing the skill, optionally run:

```sh
npx skills add dropshipcalendar/amazon-shopping-skills --list
```

This may download and execute the installer itself; it does not run the Amazon workflow. Before releases, review private-data exclusions and links, test in recipient environments, and review licensing. This repository does not currently include a license file. Edits to a separately installed copy do not update this repository automatically.
