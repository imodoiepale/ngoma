# One canonical skill source, mirrored to every runtime that reads skills.
.PHONY: skills-sync graph plan check

skills-sync:
	@mkdir -p .claude/skills .agents/skills
	@cp -r shared-skills/approved/* .claude/skills/ 2>/dev/null || true
	@cp -r shared-skills/approved/* .agents/skills/ 2>/dev/null || true
	@echo "approved skills mirrored to .claude/skills and .agents/skills"

graph:
	@uv run packages/library/graph_build.py

plan:
	@uv run --with pyyaml packages/image-router/router.py --plan-all

# Refuse to proceed if anything secret-shaped is tracked.
check:
	@git grep -inE "apik_[A-Za-z0-9]{8}|rpa_[A-Z0-9]{20}|BEGIN OPENSSH PRIVATE" -- . \
	  ':(exclude)docs/*' ':(exclude)shared-skills/*' ':(exclude).claude/*' \
	  && (echo "SECRET-SHAPED CONTENT TRACKED" && exit 1) || echo "no secrets tracked"
