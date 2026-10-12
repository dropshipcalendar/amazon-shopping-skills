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

Select the appropriate agent when prompted. Omit `--global` for a project-local installation; add `--copy` if symbolic links are unavailable. The installer currently requires Node.js 22.20.0 or newer; see its [current requirements](https://github.com/vercel-labs/skills/blob/main/package.json) and [installation options](https://github.com/vercel-labs/skills#install-a-skill). Installing the files does not install Python dependencies or run the workflow.

### Copy-and-paste setup instruction

> Download and extract https://github.com/dropshipcalendar/amazon-shopping-skills, or use your compatible skill installer to install its amazon-shopping-account skill. Read skills/amazon-shopping-account/SKILL.md from the complete local folder. Use your available computer and terminal tools to check prerequisites and help configure the required runtime and credentials securely. Do not start browsing, create accounts or inboxes, allocate phone numbers, or schedule anything until I explicitly ask.

## Required computer capabilities

- Windows or macOS with Google Chrome and Python 3.11 or newer.
- Browser or mouse/keyboard/screenshot tools that can identify and control a dedicated Chrome profile.
- Ability to read/write local files and run Python commands, directly or through a terminal window.
- The user's account name, marketplace, timezone, and secure access to the registration password. Product search names are bundled.
- AgentMail credentials; TextVerified credentials and an approved spending cap if SMS is needed.

Follow [platform setup](skills/amazon-shopping-account/references/platform.md) to create a private Python environment with the pinned [requirements](skills/amazon-shopping-account/scripts/requirements.txt). Resolve the installed skill's actual path on the recipient's computer.

Credentials are read from `AGENTMAIL_API_KEY`, `TEXTVERIFIED_API_KEY`, and `TEXTVERIFIED_API_USERNAME`. Follow [credential setup](skills/amazon-shopping-account/references/credentials.md) to provide them privately. Never paste secrets into chat, commit them, or put them in command arguments. An existing secret manager must inject the values into the actual helper process; merely saving a key in an OS vault is insufficient. Missing credentials are a setup requirement, not permission to provision another provider account.

## How the two days continue

Progress lives in local state files, so the agent does not need to remember a previous conversation. See [continuation and scheduling](skills/amazon-shopping-account/references/scheduling.md).

- **Automatic:** If an available scheduler can resume the agent or invoke a verified agent runner with access to the same files, credentials, and browser profile, the agent records that task's ID and removes it after completion. A timer that only launches a page or runs a helper is insufficient.
- **Manual:** Without those capabilities, the agent saves Day 1 and provides a dated resume instruction. Give it to a compatible computer-using agent on or after the eligible date. A reminder is not automatic execution.

Downloading or installing the skill starts neither mode. A later explicit request to run it sets the execution scope. If unattended completion is essential, establish those capabilities before starting. Windows/macOS launcher behavior has offline tests; live browser and scheduler compatibility must be verified in each environment.

## Private runtime data

Account state and Chrome profiles are stored outside the skill folder:

- Windows: `%LOCALAPPDATA%/AmazonShoppingSkill`
- macOS: `~/Library/Application Support/AmazonShoppingSkill`

Do not publish or share those directories. Each user has their own credentials, profile, state, and optional scheduled task. The skill preserves progress and prevents repeating uncertain actions; it cannot guarantee account acceptance by Amazon.

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

Use that environment's interpreter path or `python3` where appropriate. Tests use temporary state and fake providers/schedulers, not live account creation.

To check discovery without installing the skill, optionally run:

```sh
npx skills add dropshipcalendar/amazon-shopping-skills --list
```

This may download and execute the installer itself; it does not run the Amazon workflow. Before releases, review private-data exclusions and links, test in recipient environments, and review licensing. This repository does not currently include a license file. Edits to a separately installed copy do not update this repository automatically.
