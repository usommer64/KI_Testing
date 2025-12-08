import os
import tempfile
import sys

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

    assert repo_url.startswith("https://"), "repo_url must start with https://"
    # Insert credentials into URL for HTTPS cloning. Be careful not to print the token.
    repo_url_with_creds = repo_url.replace("https://x-access-token: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@github.com/usommer64/KI_Testing.git", f"https://{token}@")
    with tempfile.TemporaryDirectory() as dname:
        print("Cloning", repo_url, "to", dname)
        git.Repo.clone_from(repo_url_with_creds, dname, branch=branch)
        # Print the file list (safe), do not print the token
        return os.listdir(dname)


@app.local_entrypoint()
def main(repo_url: str):
    # note: get_username.remote() and clone_repo.remote(...) return modal.ObjectRefs (async)
    # Print the remote call objects; Modal's CLI / logs will show the actual results.
    print("Triggering remote function: get_username()")
    user_ref = get_username.remote()
    print("Triggering remote function: clone_repo()")
    repo_ref = clone_repo.remote(repo_url)
    # If you want their values locally, call .get() (this will wait)
    print("Github username (ObjectRef):", user_ref)
    print("Repo files (ObjectRef):", repo_ref)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python github_clone_repo.py https://github.com/usommer64/KI_Testing")
        sys.exit(1)
    main(sys.argv[1])