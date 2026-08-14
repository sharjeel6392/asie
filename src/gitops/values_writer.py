"""Write model versions into the GitOps values file — the deploy mechanism.

This is the piece that makes the loop closed. `export_models()` puts weights in
S3 and `promote_to_primary()` records a decision in the registry, but neither
changes what is serving: ArgoCD reconciles from git, so a model is deployed
exactly when its run_id is committed to gitops/values/inference.yaml.

Used by both promotion and automated rollback, which are the same operation in
opposite directions.

Deliberately surgical: this edits ONE key in ONE file with a regex rather than
round-tripping the YAML. `yaml.safe_load` + `safe_dump` would silently discard
every comment in that file, and those comments are the only record of why the
values are what they are (see gitops/values/inference.yaml, which explains the
S3 layout dependency that makes rollback possible at all). A values file that
loses its reasoning on the first automated commit is worse than one edited by
pattern match.
"""

import os
import re
import subprocess
import tempfile

from src.logger import configure_logger

# Where the deployed versions live, relative to the repo root.
VALUES_PATH = "gitops/values/inference.yaml"

# Author for automated commits. Distinct from any human so `git log` shows at a
# glance which deploys were decided by policy and which by a person.
BOT_NAME = "ASIE Promoter"
BOT_EMAIL = "asie-promoter@users.noreply.github.com"


class GitOpsWriteError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: str, env: dict | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise GitOpsWriteError(
            f"{' '.join(cmd[:3])} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def set_model_version(content: str, key: str, version: str) -> str:
    """Replace `key: "..."` under the model: block, preserving the line's comment.

    Pure string function so the substitution is testable without a repo, a
    network, or credentials — which is most of what makes this module safe to
    change later.
    """
    pattern = re.compile(
        rf'^(?P<indent>\s+){re.escape(key)}:\s*"(?P<old>[^"]*)"(?P<trailing>.*)$',
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        raise GitOpsWriteError(f'no `{key}: "..."` line found in {VALUES_PATH}')

    def repl(m: re.Match) -> str:
        return f'{m.group("indent")}{key}: "{version}"{m.group("trailing")}'

    updated, count = pattern.subn(repl, content, count=1)
    if count != 1:
        raise GitOpsWriteError(f"expected exactly one {key} line, replaced {count}")
    return updated


def _ssh_env(key_path: str) -> dict:
    env = os.environ.copy()
    # StrictHostKeyChecking=no because this runs unattended in a pod with no
    # known_hosts and no human to accept a fingerprint. The risk is accepting a
    # spoofed github.com; the mitigation is that the deploy key is scoped to
    # one repository, so a successful spoof gains an attacker nothing it could
    # not already read.
    env["GIT_SSH_COMMAND"] = (
        f"ssh -i {key_path} -o StrictHostKeyChecking=no -o IdentitiesOnly=yes"
    )
    return env


def update_deployed_version(
    *,
    key: str,
    version: str,
    message: str,
    repo_url: str | None = None,
    branch: str | None = None,
    ssh_key_path: str | None = None,
    push: bool = True,
) -> str | None:
    """Clone, edit one version key, commit and push. Returns the commit sha.

    Returns None when the file already names `version` — re-committing an
    identical value would produce an empty commit, and under `selfHeal` a
    stream of no-op commits is indistinguishable in `git log` from real deploy
    activity.

    A fresh shallow clone each time, rather than a long-lived working copy: the
    task runs in an ephemeral pod, and a stale checkout would silently commit
    against an old base and clobber a concurrent change.
    """
    logger = configure_logger()
    repo_url = repo_url or os.getenv("ASIE_GITOPS_REPO_URL")
    branch = branch or os.getenv("ASIE_GITOPS_BRANCH", "main")
    ssh_key_path = ssh_key_path or os.getenv("ASIE_GITOPS_SSH_KEY", "/etc/asie-gitops/ssh-privatekey")

    if not repo_url:
        raise GitOpsWriteError("ASIE_GITOPS_REPO_URL is not set")
    if not os.path.exists(ssh_key_path):
        raise GitOpsWriteError(f"deploy key not found at {ssh_key_path}")

    env = _ssh_env(ssh_key_path)

    with tempfile.TemporaryDirectory() as work:
        _run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, work], cwd=".", env=env)

        values_file = os.path.join(work, VALUES_PATH)
        with open(values_file, encoding="utf-8") as f:
            content = f.read()

        updated = set_model_version(content, key, version)
        if updated == content:
            logger.info("%s already at %s — nothing to commit", key, version)
            return None

        with open(values_file, "w", encoding="utf-8", newline="") as f:
            f.write(updated)

        _run(["git", "config", "user.name", BOT_NAME], cwd=work)
        _run(["git", "config", "user.email", BOT_EMAIL], cwd=work)
        _run(["git", "add", VALUES_PATH], cwd=work)
        _run(["git", "commit", "-m", message], cwd=work)
        sha = _run(["git", "rev-parse", "HEAD"], cwd=work).strip()

        if push:
            _run(["git", "push", "origin", f"HEAD:{branch}"], cwd=work, env=env)
            logger.info("pushed %s -> %s (%s)", key, version, sha[:8])
        else:
            logger.info("built commit %s (push disabled)", sha[:8])

        return sha
