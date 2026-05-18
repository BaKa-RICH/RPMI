---
id: "agent/references/repo-modes"
version: "1.0.0"
purpose: >
  Defines the 3 repository modes (local, github, other-git), the 20-feature
  toggle matrix, auto-detection logic with regex patterns, CI/CD pipeline
  templates per mode, mode transition rules, and integration with the
  workflow system.
triggers:
  - "detecting repository mode"
  - "configuring mode-specific features"
  - "setting up CI/CD"
tier: 2
token_estimate: 3800
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Repository Modes Reference

## 1. Mode Definitions
From §1:

| Aspect | Local | GitHub | Other-Git |
|--------|-------|--------|-----------|
| **When to use** | Personal, experiments, offline, prototypes | Open-source, team projects on GitHub | GitLab, Gitea, Bitbucket, self-hosted |
| **Remote origin** | None | `github.com` | `gitlab.com`, self-hosted, etc. |
| **Build verification** | Local only | GitHub Actions CI matrix | Platform-native CI |
| **Test execution** | Local only | GitHub Actions cross-platform | Platform-native CI |
| **Documentation** | Generated locally, not published | Auto-gen README + UserGuide, Pages | Platform Pages or self-hosted |
| **Code review** | Self-review via local diff | PR-based with required reviews | MR (GitLab) or PR flow |
| **Release workflow** | None | Tag → Build → Test → Publish | Tag → Pipeline → Registry |
| **CI/CD** | None | GitHub Actions | Platform-native config |
| **CHANGELOG** | Optional manual | Auto-generated from commits | Auto-generated |
| **Complexity** | Minimal | Full-featured | Adaptive |
| **Best for** | Prototyping, learning | Open-source, team projects | Corporate, self-hosted |

### Other-Git Variants

| Variant | Platform | CI Config | Review Flow | Registry |
|---------|----------|-----------|-------------|----------|
| `gitlab` | GitLab (cloud/self-hosted) | `.gitlab-ci.yml` | Merge Request | GitLab Package/Container Registry |
| `gitea` | Gitea / Forgejo | `.gitea/workflows/` | Pull Request | Gitea Packages |
| `codeberg` | Codeberg (Forgejo-hosted) | `.forgejo/workflows/` or `.gitea/workflows/` | Pull Request | Codeberg Pages / attachments |
| `bitbucket` | Bitbucket | `bitbucket-pipelines.yml` | Pull Request | Bitbucket Downloads |
| `generic` | Any other Git host | Manual / Makefile | Email patches / Web UI | Manual upload |

> **Note on Codeberg**: Codeberg is a managed Forgejo instance operated by a non-profit. Treat it as a `codeberg` variant (detection regex `codeberg\.org[:/]` in §3) that inherits Gitea/Forgejo pipeline semantics but pins `.forgejo/workflows/` as the preferred CI config path.

## 2. Feature Matrix (20 Features × 3 Modes)
From §2:

| # | Feature | Local | GitHub | Other-Git |
|---|---------|-------|--------|-----------|
| 1 | CI/CD Pipeline | disabled | enabled | enabled |
| 2 | Cross-Platform Build Matrix | disabled | enabled | optional |
| 3 | README Generation | optional | enabled | optional |
| 4 | UserGuide Generation | optional | enabled | optional |
| 5 | Pages / Doc Hosting | disabled | enabled | optional |
| 6 | Online Demo Hosting | disabled | enabled | disabled |
| 7 | Release Workflow | disabled | enabled | enabled |
| 8 | CHANGELOG Auto-Generation | disabled | enabled | enabled |
| 9 | Code Review Flow (PR/MR) | disabled | enabled | enabled |
| 10 | Registry Publish | disabled | optional | optional |
| 11 | Issue Tracking Integration | disabled | enabled | optional |
| 12 | Dependency Update Automation | disabled | enabled | optional |
| 13 | Security Scanning | optional | enabled | optional |
| 14 | Badge Generation | disabled | enabled | optional |
| 15 | Local Build Verification | enabled | enabled | enabled |
| 16 | Local Test Execution | enabled | enabled | enabled |
| 17 | Local Documentation Gen | enabled | enabled | enabled |
| 18 | Conventional Commits | optional | enabled | enabled |
| 19 | Branch Protection Rules | N/A | enabled | optional |
| 20 | Container Image Build | disabled | optional | optional |

**Legend:** `enabled` = active by default, `disabled` = not available,
`optional` = user-activated, `N/A` = not applicable.

## 3. Detection Logic
From §3:

### Detection Algorithm

```
function detect_repo_mode(repo_path):
    if not exists(repo_path / ".git"):
        return Local

    remotes = parse_git_remotes(git_config)
    if remotes is empty:
        return Local

    origin_url = remotes.get("origin") ?? remotes.values().first()
    variant = match_platform(origin_url)

    match variant:
        GitHub    → return GitHub
        GitLab    → return OtherGit(variant: "gitlab")
        Gitea     → return OtherGit(variant: "gitea")
        Bitbucket → return OtherGit(variant: "bitbucket")
        Unknown   → return OtherGit(variant: "generic")
```

### Regex Patterns

| Platform | HTTPS Example | SSH Example | Regex |
|----------|---------------|-------------|-------|
| GitHub | `https://github.com/owner/repo` | `git@github.com:owner/repo` | `github\.com[:/]` |
| GitLab (cloud) | `https://gitlab.com/owner/repo` | `git@gitlab.com:owner/repo` | `gitlab\.com[:/]` |
| GitLab (self-hosted) | `https://gitlab.corp.io/owner/repo` | `git@gitlab.corp.io:owner/repo` | `gitlab\.[a-z]+\.[a-z]+[:/]` |
| Gitea/Forgejo | `https://gitea.example.com/owner/repo` | — | `gitea\.\|forgejo\.` |
| Codeberg | `https://codeberg.org/owner/repo` | `git@codeberg.org:owner/repo` | `codeberg\.org[:/]` |
| Bitbucket | `https://bitbucket.org/owner/repo` | `git@bitbucket.org:owner/repo` | `bitbucket\.org[:/]` |

### URL Normalization

```
function normalize_git_url(url):
    url = url.strip().trim_suffix(".git")
    if url.starts_with("git@"):       strip "git@"
    elif url.starts_with("https://"):  strip "https://"
    elif url.starts_with("ssh://"):    strip "ssh://" then strip user@ prefix
    return url.to_lowercase()
```

### CI Config File Fallback

When URL doesn't match known patterns, check repo root for CI config files:

| File/Dir | Platform |
|----------|----------|
| `.gitlab-ci.yml` | GitLab |
| `.gitea/workflows/` or `.forgejo/workflows/` | Gitea |
| `bitbucket-pipelines.yml` | Bitbucket |
| `.github/workflows/` | GitHub |

### User Override

```yaml
# .workflow/config.yaml
repo_mode: github          # local | github | other-git
platform_variant: null     # gitlab | gitea | bitbucket | generic
features:
  cross_platform_build: true
  pages_deployment: true
  registry_publish: false
```

Override priority: **explicit config > auto-detection > default (local)**

## 4. CI/CD Pipeline Templates
From §4:

### Local Mode Pipeline

```
Code Change → Local Lint & Format → Local Build → Local Test → Doc Gen → Git Commit
```

```makefile
.PHONY: check build test doc all
check:
	cargo fmt --check
	cargo clippy -- -D warnings
build:
	cargo build --release
test:
	cargo test --release
doc:
	cargo doc --no-deps --release
all: check build test doc
```

### GitHub Mode Pipelines

**CI Pipeline (push/PR):**
```
Push/PR → Lint & Format → Build Matrix → Test Matrix → Coverage → Deploy Docs
```

**Release Pipeline (tag v*):**
```
Tag → Build Artifacts → Full Tests → CHANGELOG → GitHub Release → Registry → Pages
```

**Key config files:** `.github/workflows/ci.yml`, `.github/workflows/release.yml`

**Build matrix targets:** `x86_64-linux-gnu`, `aarch64-linux-gnu`,
`x86_64-apple-darwin`, `aarch64-apple-darwin`, `x86_64-pc-windows-msvc`

### GitLab Variant Pipeline

```
Push/MR → Lint → Build → Test → Coverage → Pages (main only)
Tag → Build Artifacts → Tests → CHANGELOG → Registry → Release
```

**Config:** `.gitlab-ci.yml` with stages: check, build, test, deploy, release

### Gitea Variant Pipeline

**Config:** `.gitea/workflows/ci.yml` (GitHub Actions compatible format)

## 5. Mode Transition Rules
From §5.1:

```
          git init (no remote)
[*] ──────────────────────────► Local
                                  │
         git remote add github.com│    git remote add gitlab.com
                  ┌───────────────┤────────────────────┐
                  ▼               │                    ▼
              GitHub ◄────────────┼──────────────► OtherGit
                  │   change remote│                   │
                  │               │                    │
                  └───────────────┼────────────────────┘
                  remove remotes  │  remove remotes
                                  ▼
                               Local
```

### Mode Initialization Actions

| Transition | Generated Files |
|------------|----------------|
| → Local | Makefile/Justfile, local gate script |
| → GitHub | `.github/workflows/ci.yml`, `.github/workflows/release.yml`, PR template, issue templates, `CODEOWNERS` |
| → Other-Git (GitLab) | `.gitlab-ci.yml`, MR template, issue templates |
| → Other-Git (Gitea) | `.gitea/workflows/ci.yml`, PR template |
| → Other-Git (Bitbucket) | `bitbucket-pipelines.yml` |

## 6. Integration with Workflow System
From §6:

### Mode in Pre-Decision Phase

1. Auto-detect repository mode from `.git/config`
2. Present detected mode and features to user
3. Ask for confirmation or override
4. Collect mode-specific configuration

### Mode-Aware Stage Behavior

| Stage | Local Mode | GitHub Mode | Other-Git Mode |
|-------|-----------|-------------|----------------|
| **Implement** | Local build/test gate | Local + CI trigger | Local + CI trigger |
| **Review** | Self-review checklist | PR creation + reviewer | MR/PR creation |
| **Test** | Local test suite | CI matrix + coverage upload | CI test + coverage |
| **Gate** | Local gate script | CI status checks | CI pipeline status |
| **Release** | Skip (no release) | Tag → Actions → Release | Tag → CI → Registry |
| **Deploy** | Skip (no deploy) | Pages deployment | Pages / self-hosted |
| **+verify** | `make check` local | CI status + branch protection assertions | CI status + MR/PR approval assertions |
| **+monitor** | Skip (no telemetry) | `.github/workflows/monitor.yml` + Actions metrics | Platform-native webhooks + Grafana/self-hosted |

### Configuration Schema

```yaml
# .workflow/repo-mode.yaml
mode: github
variant: null
detected_from: origin
detection_method: url_pattern  # url_pattern | ci_config_file | api_probe | user_override

features:
  ci_cd: true
  cross_platform_build: true
  readme_generation: true
  pages_deployment: true
  release_workflow: true
  changelog_generation: true
  code_review_flow: true
  registry_publish: false
  security_scanning: true

platform_config:
  default_branch: main
  branch_protection: true
  required_reviewers: 1
  release_tag_pattern: "v*"
  changelog_tool: git-cliff
  artifact_targets:
    - x86_64-unknown-linux-gnu
    - aarch64-apple-darwin
    - x86_64-pc-windows-msvc
```

## 7. Plugin / Tool Interaction with Mode Detection

DevolaFlow plugins and tooling consult the detected repo mode to gate
platform-specific behaviour. Mode detection runs once per agent session and
caches the result in `.workflow/repo-mode.yaml`; plugins read this file (or
the in-memory `RepoModeProfile`) rather than re-running detection.

**Canonical consumers (v9.0.0 baseline):**

| Plugin / Tool | Mode-gated behaviour | Fallback when mode absent |
|---|---|---|
| `agent_workspace` | Records `repo_mode` in change-folder `STATUS.yaml`; skips GitHub-specific PR metadata emission in `local` / `other-git` | Treat as `local` (safe default) |
| `shell_proxy` | Enables `gh` command recipes only in `github` mode; enables `glab` recipes in `other-git` `gitlab` variant | Skip platform-specific recipes |
| `mergeability_check` | Probes `gh pr view` / `glab mr show` / `tea pr list` based on mode variant | Reject the probe (no remote API) |
| Adapter build | Selects default release channel per mode (`github` → GitHub Releases; `other-git gitlab` → GitLab Package Registry; `local` → artifact archive only) | Fall through to archive-only |
| EvoBench harness | Enables `--upload-baseline` only in `github` mode with CI token; local runs keep baselines on disk | Disk-only mode |

Plugins MUST degrade gracefully when mode detection returns `local` or when
a mode-specific tool (`gh`, `glab`, `tea`) is unavailable — per Soul rule
S-5 (No Silent Failures), the plugin logs the skip reason and returns a
structured no-op result rather than crashing the parent dispatch.
