# Copilot Instructions for KI_Testing

## Project Purpose
Learning repository for Modal + GitHub integration patterns. Main use case: demonstrating authenticated GitHub operations from Modal serverless functions.

## Architecture Overview
- **[github_clone_repo.py](../github_clone_repo.py)**: Modal application with two remote functions
  - `get_username()`: Validates GitHub API access via PyGithub
  - `clone_repo()`: Clones repos using GitPython with credentialized URLs
- **Dev Container**: Python 3.10.12 environment with git, curl, Docker extension

## Critical Workflows

### Running the Modal App
```bash
modal run github_clone_repo.py https://github.com/OWNER/REPO
```
Triggers remote functions, prints username and cloned file list.

### Secret Management Pattern
- Modal secret name: `github-secret`
- Environment variable lookup order: `GITHUB_TOKEN` → `GITHUB_PAT` → `GITHUB`
- Helper function `_get_token_from_env()` searches these in order
- **Never** print tokens or clone URLs in logs

## Project-Specific Conventions

### Token URL Construction
Use `make_clone_url_with_token()` for safe HTTPS clone URLs:
- Username: `x-access-token` (GitHub standard)
- Token: URL-quoted via `urllib.parse.quote(token, safe="")`
- Format: `https://x-access-token:{token}@github.com/OWNER/REPO.git`
- Always ensure `.git` suffix on paths

### Modal Image Strategy
- **pygithub_image**: Debian slim + PyGithub>=1.59 for API calls
- **git_image**: Debian slim + git + GitPython for cloning
- Separate images keep dependencies lean per function

### Error Handling Pattern
- Assert `https://` scheme on repo URLs (line 70)
- Raise `RuntimeError` if no GitHub token found in environment
- Use temporary directories for cloning (auto-cleanup with context manager)

## Key Dependencies
- **modal**: Serverless compute platform (secrets, images, remote functions)
- **PyGithub>=1.59**: GitHub API wrapper for authentication
- **GitPython**: Git operations in Python

## Dev Container Setup
- Python packages installed via `.devcontainer/requirements.txt` (currently empty)
- Post-create command: `pip install -r requirements.txt`
- Extensions: Python, Docker

## Documentation References
- [README_for_github_clone_repo.md](../README_for_github_clone_repo.md): Beginner-friendly guide to Modal secrets, PAT creation, and running the example
