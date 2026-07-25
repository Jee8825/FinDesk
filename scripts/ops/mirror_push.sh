#!/usr/bin/env bash
# Snapshot-and-mirror the working tree to the hackathon remote.
#
# Run by a launchd agent every 2h (see scripts/ops/com.findesk.mirror-push.plist).
# Commits any uncommitted work on the current branch as a WIP snapshot, then
# pushes every local branch + tags to $REMOTE. Refuses to act mid-rebase/merge.
#
# Manual run:  scripts/ops/mirror_push.sh
# Logs to:     var/mirror-push.log   (gitignored)

set -uo pipefail

REPO="/Users/Jee/Hackathon/FInDesk"
REMOTE="${MIRROR_REMOTE:-hackathon}"
LOG="$REPO/var/mirror-push.log"
LOCK="$REPO/var/mirror-push.lock"

cd "$REPO" || exit 1
mkdir -p "$REPO/var"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" >>"$LOG"; }

# Single instance. mkdir is atomic; stale locks older than 30m are reclaimed.
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    log "reclaiming stale lock"
    rmdir "$LOCK" 2>/dev/null && mkdir "$LOCK" 2>/dev/null || { log "lock busy, skipping"; exit 0; }
  else
    log "another run in progress, skipping"
    exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# Homebrew git/gh are not on launchd's default PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

git rev-parse --git-dir >/dev/null 2>&1 || { log "ERROR not a git repo"; exit 1; }

# Never commit on top of an in-progress history rewrite.
GIT_DIR_PATH="$(git rev-parse --git-dir)"
for marker in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
  if [ -e "$GIT_DIR_PATH/$marker" ]; then
    log "SKIP operation in progress ($marker)"
    exit 0
  fi
done
if [ -n "$(git ls-files --unmerged)" ]; then
  log "SKIP unresolved merge conflicts"
  exit 0
fi

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [ -z "$BRANCH" ]; then
  log "SKIP detached HEAD"
  exit 0
fi

git remote get-url "$REMOTE" >/dev/null 2>&1 || { log "ERROR remote '$REMOTE' not configured"; exit 1; }

# Snapshot uncommitted work (respects .gitignore, so .env and var/ stay out).
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  if git diff --cached --quiet; then
    log "nothing staged after add (ignored files only)"
  else
    FILES="$(git diff --cached --name-only | wc -l | tr -d ' ')"
    if git commit --quiet -m "chore(snapshot): auto-commit WIP on $BRANCH ($FILES file(s))

Automated 2-hourly snapshot from scripts/ops/mirror_push.sh." ; then
      log "committed snapshot on $BRANCH ($FILES file(s)) -> $(git rev-parse --short HEAD)"
    else
      log "ERROR commit failed"
      exit 1
    fi
  fi
else
  log "tree clean on $BRANCH"
fi

# Push every local branch + tags. Non-forced: a rejected ref is logged, not forced.
OUT="$(git push --all --porcelain "$REMOTE" 2>&1)"; RC=$?
if [ $RC -eq 0 ]; then
  UPDATED="$(printf '%s\n' "$OUT" | grep -cE '^\s*[*+ ]?refs/heads/' || true)"
  log "pushed branches to $REMOTE (ok, $UPDATED ref line(s))"
else
  log "ERROR branch push rc=$RC: $(printf '%s' "$OUT" | tr '\n' ' | ')"
fi

TOUT="$(git push --tags "$REMOTE" 2>&1)"; TRC=$?
if [ $TRC -eq 0 ]; then
  log "pushed tags to $REMOTE (ok)"
else
  log "ERROR tag push rc=$TRC: $(printf '%s' "$TOUT" | tr '\n' ' | ')"
fi

log "head=$(git rev-parse --short HEAD) branch=$BRANCH done"
exit $RC
