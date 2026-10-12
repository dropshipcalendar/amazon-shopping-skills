# Amazon Shopping Account skill

A reusable agent skill for one user-owned Amazon shopping account. Day 1 browses the bundled 50-product allowlist while signed out for five minutes and adds at most two matching products to the cart. Day 2 registers the account in the same dedicated Chrome profile, using AgentMail and, only when requested by Amazon, one-time TextVerified SMS. It does not place orders.

This repository distributes a standalone skill through `npx skills add`. No plugin marketplace or custom npm package is required. The `skills` npm package is the installer; this repository contains the skill it installs.

## Install

Repository: [dropshipcalendar/amazon-shopping-skills](https://github.com/dropshipcalendar/amazon-shopping-skills).

Install [Node.js](https://nodejs.org/) with npm/npx. The installer currently requires Node.js 22.20.0 or newer; check its [current requirements](https://github.com/vercel-labs/skills/blob/main/package.json) if installation reports a version mismatch.

Run this in a terminal, then select your agent:

```sh
npx skills add dropshipcalendar/amazon-shopping-skills --skill amazon-shopping-account --global
```

Alternatively, target Codex directly:

```sh
npx skills add dropshipcalendar/amazon-shopping-skills --skill amazon-shopping-account --agent codex --global
```

Use one installation method. `--global` makes the skill available across projects; omit it for a project-local installation. If symbolic links are unavailable, add `--copy`. See the [installer documentation](https://github.com/vercel-labs/skills#install-a-skill) for supported agents and options.

The same installer supports Claude Code and other agents, but installation support is not execution compatibility. This skill's full two-day scheduling flow currently targets Codex desktop with a same-chat scheduler. Equivalent scheduling and browser tools have not been validated in other agents. Restart the agent if the installed skill does not appear.

### Copy-and-paste instruction for an agent

Give your agent this instruction:

> Install the Amazon Shopping Account skill by running `npx skills add dropshipcalendar/amazon-shopping-skills --skill amazon-shopping-account --global` and selecting this agent. Read the installed SKILL.md and report missing runtime requirements. Installation only: do not create provider inboxes, allocate phone numbers, launch the Amazon workflow, or create a schedule.

## Runtime setup

Installing the skill copies its instructions and supporting files. It does not install its Python dependencies, configure credentials, create an account, or schedule either day.

The full workflow needs:

- Windows or macOS, Google Chrome, and Python 3.11 or newer.
- A compatible browser-control tool connected to the dedicated Chrome session.
- Codex desktop's same-chat scheduling capability and a machine/app available when the continuation runs.
- AgentMail credentials; TextVerified credentials and an explicitly approved spending cap if SMS is needed.
- The user's account name, a supported marketplace, timezone, desired Day 2 time, and secure access to the registration password. Product names are already bundled.

Ask the agent to follow [platform setup](skills/amazon-shopping-account/references/platform.md) and create a private Python environment with the pinned [requirements](skills/amazon-shopping-account/scripts/requirements.txt). Use the installed skill's actual path; paths in this repository are not paths on the recipient's computer.

Credential variable names:

| Variable | Used for |
| --- | --- |
| `AGENTMAIL_API_KEY` | Email inbox and verification |
| `TEXTVERIFIED_API_KEY` | Conditional one-time SMS |
| `TEXTVERIFIED_API_USERNAME` | Conditional one-time SMS |

Follow [credential setup](skills/amazon-shopping-account/references/credentials.md). Supply values privately through an approved secret-manager launcher or local environment; never paste them into chat, commit them, or include them in commands. The helpers do not automatically read Windows Credential Manager or macOS Keychain. Unattended Day 2 requires credentials to reach the actual scheduled process; a one-time hidden terminal prompt is not enough. Missing credentials are a setup requirement, not permission to create another provider account.

The skill keeps account state and Chrome profiles outside its installation directory:

- Windows: `%LOCALAPPDATA%\AmazonShoppingSkill`
- macOS: `~/Library/Application Support/AmazonShoppingSkill`

Do not publish or share those directories. Each recipient uses their own credentials, account state, profile, and automation ID.

## Use after setup

Invoke `amazon-shopping-account` through your agent's skill selector. In Codex, you can mention `$amazon-shopping-account`.

A setup-only request:

> Use $amazon-shopping-account to check the prerequisites for my computer. Do not start browsing, create accounts, allocate SMS numbers, or schedule anything yet.

A later explicit request to run the full workflow authorizes the skill's two-day flow. The agent obtains missing configuration, verifies browser and credential access, and records the same-chat continuation before starting Day 1. See [the skill](skills/amazon-shopping-account/SKILL.md) and [scheduling details](skills/amazon-shopping-account/references/scheduling.md).

This is local automation guidance, not a hosted signup service. Runtime/browser compatibility and live provider behavior must be verified on the recipient's machine. The bundled offline tests do not establish live Amazon acceptance or Mac browser-control availability.

## Repository contents

```text
amazon-shopping-skills/
├── README.md
├── .gitignore
└── skills/
    └── amazon-shopping-account/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── assets/
        ├── references/
        ├── scripts/
        └── tests/
```

Keep the whole skill folder together. Installing only the raw `SKILL.md` would omit the required helpers and product allowlist. The skill's `name` remains `amazon-shopping-account`, matching the `--skill` argument.

## Maintainer checks before publishing

1. Confirm the repository identity and review licensing before each release. This repository does not currently include a license file.
2. Review the files for credentials, account records, browser data, and personal paths. Ignore rules are a backstop, not a replacement for review.
3. Run the offline tests using a Python environment with `skills/amazon-shopping-account/scripts/requirements.txt` installed:

   ```sh
   python -m unittest discover -s skills/amazon-shopping-account/tests -v
   ```

   On macOS, use the selected Python interpreter's path or `python3` if appropriate. Tests use temporary state and fake providers/scheduler responses; they do not perform the live workflow.

4. To inspect local skill discovery without installing this skill, run from this repository root:

   ```sh
   npx skills add . --list
   ```

   This may download and execute the installer itself; it does not run the Amazon workflow.

5. After publication, check discovery through the real repository URL with `--list`, then test installation in a clean recipient environment. Validate Windows and macOS browser/scheduling behavior separately before claiming support.

The copy in this repository is a distribution snapshot. Edits to an already installed personal copy do not automatically update it; keep the repository version current before releasing updates.

## Sources

- [Skills installer: commands, scopes, and supported agents](https://github.com/vercel-labs/skills)
- [Installer Node.js requirement](https://github.com/vercel-labs/skills/blob/main/package.json)
- [OpenAI: build and distribute skills](https://learn.chatgpt.com/docs/build-skills)

Installation documentation checked on 2026-10-12.
