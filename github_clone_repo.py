
#%%
import os
import tempfile
import sys
from urllib.parse import urlparse, urlunparse, quote

import modal

app = modal.App()
pygithub_image = modal.Image.debian_slim().pip_install("PyGithub>=1.59")
git_image = modal.Image.debian_slim().apt_install("git").pip_install("GitPython")


def _get_token_from_env():
    # Check common env var names that might be used for your secret
    for name in ("GITHUB_TOKEN", "GITHUB_PAT", "GITHUB"):
        val = os.environ.get(name)
        if val:
            return val, name
    return None, None


def make_clone_url_with_token(repo_url: str, token: str, username: str = "x-access-token") -> str:
    """
    Construct a credentialized HTTPS clone URL using the x-access-token username.

    Example output:
      https://x-access-token:ghp_ABC123def456@github.com/OWNER/REPO.git

    The token is URL-quoted to handle any special characters safely.
    """
    parsed = urlparse(repo_url)
    scheme = parsed.scheme or "https"
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Invalid repo_url: {repo_url}")

    # Ensure path ends with .git for cloning
    path = parsed.path
    if not path.endswith(".git"):
        path = path + ".git"

    token_quoted = quote(token, safe="")  # escape any special chars
    netloc = f"{username}:{token_quoted}@{hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"

    return urlunparse((scheme, netloc, path, "", "", ""))


@app.function(image=pygithub_image, secrets=[modal.Secret.from_name("github-secret")])
def get_username():
    import github

    token, name = _get_token_from_env()
    if not token:
        raise RuntimeError(
            "No GitHub token found in environment. Expected one of GITHUB_TOKEN, GITHUB_PAT, or GITHUB.\n"
            "Make sure your Modal secret exposes the token under one of those env var names."
        )
    g = github.Github(auth=github.Auth.Token(token))
    return g.get_user().login


@app.function(image=git_image, secrets=[modal.Secret.from_name("github-secret")])
def clone_repo(repo_url, branch="main"):
    import git
    token, name = _get_token_from_env()
    if not token:
        raise RuntimeError(
            "No GitHub token found in environment. Expected one of GITHUB_TOKEN, GITHUB_PAT, or GITHUB.\n"
            "Make sure your Modal secret exposes the token under one of those env var names."
        )

    if not repo_url.startswith("https://"):
        raise AssertionError("repo_url must start with https://")

    # Build a safe clone URL with x-access-token username and URL-quoted token
    clone_url = make_clone_url_with_token(repo_url, token, username="x-access-token")

    with tempfile.TemporaryDirectory() as dname:
        # Be careful: do NOT print the clone_url or token to logs.
        print("Cloning", repo_url, "to", dname)
        git.Repo.clone_from(clone_url, dname, branch=branch)
        # List the files (safe) and return them
        return os.listdir(dname)


@app.local_entrypoint()
def main(repo_url: str):
    # Trigger the remote functions and wait for their results.
    try:
        print("Triggering remote function: get_username()")
        user_ref = get_username.remote()
        print("Triggering remote function: clone_repo()")
        repo_ref = clone_repo.remote(repo_url)

        # Wait for and retrieve results (this blocks until remote results are ready)
        username = user_ref.get()
        repo_files = repo_ref.get()

        print("Github username:", username)
        print("Repo files:")
        for f in repo_files:
            print(" -", f)

    except Exception as e:
        print("Error during remote run:", str(e))
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python github_clone_repo.py https://github.com/OWNER/REPO")
        sys.exit(1)
    main(sys.argv[1])
