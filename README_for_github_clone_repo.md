# Modal ↔ GitHub quickstart (for `github_clone_repo.py`)

This README explains, at a beginner level, how to run the `github_clone_repo.py` example that demonstrates authenticated communication between a Modal workspace and GitHub using a Personal Access Token (PAT). It covers:

- what the code does,
- how the token is supplied securely (Modal secret → environment variable),
- how to run the example both locally and inside Modal,
- how to verify that Modal actually contacted GitHub,
- safety and troubleshooting tips.

If you are new to GitHub and Modal, follow the sections in order.

---

## What this repo/example does (plain language)

The example runs two small Modal functions:

- `get_username` — calls the GitHub API (via PyGithub) and returns the GitHub username of the token owner.
- `clone_repo` — clones a GitHub repository into a temporary directory inside the Modal run and returns the file list.

Both functions authenticate to GitHub using a token (your Personal Access Token). The token is not hardcoded in the script; instead it is provided via an environment variable that Modal injects from a secret you create in the Modal workspace.

This demonstrates an authenticated request from Modal → GitHub and is a safe way to confirm the connection works.

---

## Files

- `github_clone_repo.py` — the example script you already have. It:
  - looks for the token in environment variables (GITHUB_TOKEN, GITHUB_PAT, or GITHUB),
  - constructs a safe credentialized clone URL using `x-access-token`,
  - triggers two Modal functions (get_username and clone_repo) and prints their results.

Save this file in your repo root (if not already present).

---

## Before you start: create a GitHub Personal Access Token (PAT)

If you haven't already created a PAT, create a fine‑grained token with only the permissions you need:

- Go to GitHub → Settings → Developer settings → Personal access tokens → Fine‑grained tokens → Generate new token.
- Choose "Only select repositories" and select the repo(s) this token should access.
- For cloning/reading files you typically need: Repository → Contents: Read.
- Give it a short expiration (30/90 days) and copy the generated token immediately — GitHub shows it only once.

Important: treat the token like a password — do not paste it in chats, screenshots, or commit it to your repo.

---

## Step 1 — Add the token to your Modal workspace as a secret

The code expects the Modal secret to be available under the secret name `github-secret` and the environment variable key to be `GITHUB_TOKEN` (the script also accepts `GITHUB_PAT` or `GITHUB` as fallback).

1. In the Modal web UI, open your Workspace → Settings / Workspace Management → Secrets (Modal labels vary — look for "Secrets", "Credentials", or "API Tokens").
2. Create a secret with the name `github-secret`.
3. Inside that secret, create a key/value entry:
   - Key: `GITHUB_TOKEN`
   - Value: `github_pat_XXXXXXXXXXXXXXXXXXXXXXXX` (paste your PAT)
4. Save the secret.

Note: Modal's UI may ask how to expose secret keys to runs; if there is a mapping step, make sure `GITHUB_TOKEN` becomes an environment variable when you run functions that reference `modal.Secret.from_name("github-secret")`.

---

## How the code reads the token (so you understand what's happening)

The script contains a helper `_get_token_from_env()` that checks:

- `GITHUB_TOKEN`
- `GITHUB_PAT`
- `GITHUB`

in the process environment (in that order). Modal will populate the chosen environment variable from the `github-secret` secret key you created. The functions then use the token to call GitHub.

The clone URL is built safely using `x-access-token` as username and URL‑quoting the token, so special characters are handled properly.

---

## Step 2 — Run the example in Modal (recommended)

1. Ensure `github_clone_repo.py` is in your repo or available locally.
2. Ensure the Modal workspace has the `github-secret` configured as described above.
3. Start a run from the Modal UI or use the modal CLI to run the local entrypoint:
   - In the Modal UI: create a run using `github_clone_repo.py` and supply the repo URL as the argument, for example:
     ```
     https://github.com/usommer64/KI_Testing
     ```
     Ensure the run has the `github-secret` attached (Modal typically does this automatically when you declare `secrets=[modal.Secret.from_name("github-secret")]` in code, but confirm in the run creation dialog).
   - Using the modal CLI (if configured): run the local entrypoint which will remotely execute the functions:
     ```
     modal run github_clone_repo.py https://github.com/usommer64/KI_Testing
     ```

What you should see in Modal run logs:
- A printed GitHub username (the value returned by `get_username`).
- A printed list of files (the returned list from `clone_repo`).
These confirm that Modal successfully authenticated and contacted GitHub.

---

## Step 3 — Run the example locally (for quick tests)

You can also test locally without Modal to verify your token works. This does not use Modal functions but exercises the same token usage logic.

1. On macOS/Linux:
   ```
   export GITHUB_TOKEN="github_pat_XXXXXXXXXXXXXXXX"
   python github_clone_repo.py https://github.com/usommer64/KI_Testing
   ```

2. On Windows PowerShell:
   ```
   $env:GITHUB_TOKEN = "github_pat_XXXXXXXXXXXXXXXX"
   python github_clone_repo.py https://github.com/usommer64/KI_Testing
   ```

Local tests are useful to debug before running in Modal, but remember local environments can leak tokens in shell history or logs — never paste the token into public places.

---

## How to verify GitHub saw the request

- In GitHub, go to: Settings → Developer settings → Personal access tokens → (your token)
  - GitHub will show the token's "Last used" time. After a successful Modal run that used the token, this timestamp should update to the run time.
- In Modal, open the run's logs — you should see successful outputs (status 200 from APIs or the username and file list). Modal logs + GitHub "Last used" together prove the communication took place.

---

## Security best practices (please follow)

- Never commit tokens into your repository.
- Use fine‑grained tokens limited to specific repositories and minimal permissions.
- Use short expiration and rotate tokens periodically.
- Prefer installing the Modal GitHub App (organization install) for long‑term production integrations instead of a user PAT.
- Do not print the token or credentialized clone URLs into logs. The example avoids printing the token; keep it that way.

---

## Troubleshooting

- `No GitHub token found in environment` (error from the script)
  - Confirm your Modal secret name is `github-secret` and it has a key `GITHUB_TOKEN`.
  - Confirm that when creating the run, the secret is attached/mapped so Modal exposes `GITHUB_TOKEN` to the function environment.
  - For local testing, export the environment variable in your shell before running.

- Clone fails with authentication issues (403/401)
  - Check the token permissions: does it have `Contents: Read` for the target repo?
  - Is the repo URL correct? Use `https://github.com/OWNER/REPO` (the script will add `.git` automatically).
  - Check token “Last used” and Modal run logs for status codes or error messages.

- Token still shows `Never used` after running
  - Verify the run logs show the functions ran and printed results; if the functions only access public repos they might not require auth.
  - Ensure the Modal run actually had the secret attached and the function read the token (no exceptions about missing token). If missing, fix the secret mapping and run again.

---

## Next steps and helpful commands

- To inspect the latest commits on a repo from your terminal:
  ```
  git ls-remote https://github.com/usommer64/KI_Testing
  ```
- To query a repo with curl and your token (example — do NOT paste token publicly):
  ```
  curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/repos/usommer64/KI_Testing
  ```

---

If you want, I can also:
- produce a small `modal.yml` or run script that shows exactly how to attach the secret in Modal UI/CLI,
- draft the text to request Modal GitHub App installation for your organization (if you later want to use the GitHub App route),
- or add extra example functions (create a branch, open a PR) once you are comfortable with the basics.

Save this README into your repo so you can refer to it later without opening this chat. If anything is unclear or a Modal UI field looks different, paste a screenshot and I’ll point at the exact fields to change.