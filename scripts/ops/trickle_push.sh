#!/usr/bin/env bash
# Trickle this repo to the hackathon remote in small laps, then keep it synced.
#
# Run by a launchd agent every 20 min (scripts/ops/com.findesk.mirror-push.plist).
#
# Phase 1 — BACKFILL (LAPS x 20min ~= 8h): walk a frontier forward along the
#   commit chain of $SPINE, pushing only the next slice each lap. Auxiliary
#   branches are published as the frontier reaches their tips, so the remote
#   grows commit-by-commit and ends up an exact mirror of the local branches.
#   New local commits made during the window extend the chain and are picked up.
#
# Phase 2 — SYNC (after the last lap): snapshot uncommitted work and push all
#   branches + tags, rate-limited to once every 2h.
#
# Commit dates are never rewritten; this staggers pushes, not history.
#
# Manual lap:  scripts/ops/trickle_push.sh
# Reset:       rm var/trickle-push.state
# Logs:        var/mirror-push.log        (gitignored)

set -uo pipefail

REPO="/Users/Jee/Hackathon/FInDesk"
REMOTE="${MIRROR_REMOTE:-hackathon}"
SPINE="${MIRROR_SPINE:-feat/crucible-hardening}"   # branch holding the full chain
LAPS="${MIRROR_LAPS:-24}"                          # 24 laps x 20min = 8h
SYNC_INTERVAL=7200                                 # phase-2 cadence, seconds

LOG="$REPO/var/mirror-push.log"
LOCK="$REPO/var/mirror-push.lock"
STATE="$REPO/var/trickle-push.state"
SYNCSTAMP="$REPO/var/trickle-push.lastsync"

# Homebrew git/gh are not on launchd's default PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$REPO" || exit 1
mkdir -p "$REPO/var"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" >>"$LOG"; }

# Single instance. mkdir is atomic; locks older than 30m are treated as stale.
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

git rev-parse --git-dir >/dev/null 2>&1 || { log "ERROR not a git repo"; exit 1; }
git remote get-url "$REMOTE" >/dev/null 2>&1 || { log "ERROR remote '$REMOTE' not configured"; exit 1; }

# ---------------------------------------------------------------- guards
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

# ---------------------------------------------------------------- snapshot WIP
# Commits local work so it joins the chain. Respects .gitignore, so .env and
# var/ never enter. During backfill the new commit is published by a later lap.
snapshot_wip() {
  local branch files
  branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  [ -z "$branch" ] && { log "detached HEAD, not snapshotting"; return 0; }
  [ -z "$(git status --porcelain)" ] && { log "tree clean on $branch"; return 0; }

  git add -A
  if git diff --cached --quiet; then
    log "nothing staged after add (ignored files only)"
    return 0
  fi
  files="$(git diff --cached --name-only | wc -l | tr -d ' ')"
  if git commit --quiet -m "chore(snapshot): auto-commit WIP on $branch ($files file(s))

Automated snapshot from scripts/ops/trickle_push.sh."; then
    log "committed snapshot on $branch ($files file(s)) -> $(git rev-parse --short HEAD)"
  else
    log "ERROR commit failed"
  fi
}

snapshot_wip

# ---------------------------------------------------------------- phase select
LAP=0
[ -f "$STATE" ] && LAP="$(tr -dc '0-9' <"$STATE" 2>/dev/null || echo 0)"
[ -z "$LAP" ] && LAP=0

if [ "$LAP" -ge "$LAPS" ]; then
  # ------------------------------------------------------------- phase 2: sync
  now="$(date +%s)"
  last=0
  [ -f "$SYNCSTAMP" ] && last="$(tr -dc '0-9' <"$SYNCSTAMP" 2>/dev/null || echo 0)"
  [ -z "$last" ] && last=0
  if [ $((now - last)) -lt "$SYNC_INTERVAL" ]; then
    log "sync: $(( (SYNC_INTERVAL - (now - last)) / 60 ))m until next window, skipping"
    exit 0
  fi
  out="$(git push --all "$REMOTE" 2>&1)"; rc=$?
  tout="$(git push --tags "$REMOTE" 2>&1)"; trc=$?
  if [ $rc -eq 0 ] && [ $trc -eq 0 ]; then
    printf '%s' "$now" >"$SYNCSTAMP"
    log "sync: pushed all branches + tags to $REMOTE (ok)"
  else
    log "ERROR sync rc=$rc/$trc: $(printf '%s %s' "$out" "$tout" | tr '\n' ' | ')"
  fi
  exit 0
fi

# ------------------------------------------------------------ phase 1: backfill
git rev-parse --verify --quiet "$SPINE" >/dev/null || { log "ERROR spine '$SPINE' missing"; exit 1; }

# Chain is recomputed every lap, so commits added mid-window are included.
CHAIN="$(git rev-list --reverse "$SPINE")"
TOTAL="$(printf '%s\n' "$CHAIN" | grep -c .)"
[ "$TOTAL" -eq 0 ] && { log "ERROR empty chain"; exit 1; }

LAP=$((LAP + 1))
# ceil(LAP * TOTAL / LAPS) — the frontier index for this lap.
IDX=$(( (LAP * TOTAL + LAPS - 1) / LAPS ))
[ "$IDX" -gt "$TOTAL" ] && IDX="$TOTAL"
FRONTIER="$(printf '%s\n' "$CHAIN" | sed -n "${IDX}p")"
[ -z "$FRONTIER" ] && { log "ERROR no commit at index $IDX/$TOTAL"; exit 1; }

# The frontier rides main until main's own tip, then moves to the spine, so the
# remote branch layout stays faithful to local.
MAIN_IDX="$(printf '%s\n' "$CHAIN" | grep -n "^$(git rev-parse main)$" | cut -d: -f1)"
[ -z "$MAIN_IDX" ] && MAIN_IDX=0

if [ "$MAIN_IDX" -gt 0 ] && [ "$IDX" -le "$MAIN_IDX" ]; then
  TARGET_REF="refs/heads/main"
else
  TARGET_REF="refs/heads/$SPINE"
fi

out="$(git push "$REMOTE" "${FRONTIER}:${TARGET_REF}" 2>&1)"; rc=$?
if [ $rc -eq 0 ]; then
  log "lap $LAP/$LAPS: $(git rev-parse --short "$FRONTIER") -> $TARGET_REF (commit $IDX/$TOTAL)"
  printf '%s' "$LAP" >"$STATE"
else
  log "ERROR lap $LAP/$LAPS push failed rc=$rc: $(printf '%s' "$out" | tr '\n' ' | ')"
  exit 1   # state not advanced; the next lap retries this slice
fi

# Publish auxiliary branches once the frontier has passed their tips.
while IFS= read -r b; do
  [ -z "$b" ] && continue
  [ "$b" = "main" ] && continue
  [ "$b" = "$SPINE" ] && continue
  bsha="$(git rev-parse "$b")"
  bidx="$(printf '%s\n' "$CHAIN" | grep -n "^${bsha}$" | cut -d: -f1)"
  # Not on the spine (e.g. a divergent branch): hold until the final lap.
  if [ -z "$bidx" ]; then
    [ "$LAP" -lt "$LAPS" ] && continue
  elif [ "$bidx" -gt "$IDX" ]; then
    continue
  fi
  if git push "$REMOTE" "refs/heads/$b:refs/heads/$b" >/dev/null 2>&1; then
    log "  aux: published $b @ $(git rev-parse --short "$b")"
  fi
done < <(git for-each-ref --format='%(refname:short)' refs/heads)

# main gets pinned at its own tip on the lap the frontier crosses it.
if [ "$MAIN_IDX" -gt 0 ] && [ "$IDX" -ge "$MAIN_IDX" ]; then
  git push "$REMOTE" refs/heads/main:refs/heads/main >/dev/null 2>&1 \
    && log "  aux: main pinned @ $(git rev-parse --short main)"
fi

if [ "$LAP" -ge "$LAPS" ]; then
  git push --tags "$REMOTE" >/dev/null 2>&1 && log "  tags pushed"
  log "backfill COMPLETE after $LAPS laps; switching to ${SYNC_INTERVAL}s sync mode"
fi

exit 0
