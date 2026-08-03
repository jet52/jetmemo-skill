SKILL_NAME := jetmemo
VERSION := $(shell cat VERSION)
ZIP_NAME := $(SKILL_NAME)-skill-v$(VERSION).zip
JETCITE_SRC := ../jetcite/src/jetcite
JETCITE_DEST := skill/lib/jetcite
SPLITMARKS_SRC := ../splitmarks/splitmarks.py
SPLITMARKS_DEST := skill/scripts/splitmarks.py
CITESTYLE_SRC := ../jetcite/reference/nd-citation-style.md
CITESTYLE_DEST := skill/references/nd-citation-style.md

.PHONY: package clean install test release vendor-jetcite vendor-splitmarks vendor-citestyle drift-check version-check

package: clean
	mkdir -p $(SKILL_NAME)-skill
	cp -r skill/ install.py install.sh README.md VERSION $(SKILL_NAME)-skill/
	cd $(SKILL_NAME)-skill && rm -rf .venv node_modules package-lock.json __pycache__ TODO.md
	find $(SKILL_NAME)-skill -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	zip -r $(ZIP_NAME) $(SKILL_NAME)-skill/
	rm -rf $(SKILL_NAME)-skill

# The version lives in three places that must agree: VERSION (canonical, drives
# the zip name and the release tag), the plugin manifest, and the SKILL.md
# frontmatter the model reads. v3.9.0 and v3.10.0 both shipped with only VERSION
# bumped, leaving the other two at 3.8.5; this makes that failure loud.
version-check:
	@V=$$(cat VERSION) && \
	PV=$$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' .claude-plugin/plugin.json | head -1) && \
	SV=$$(sed -n 's/^version:[[:space:]]*//p' skill/SKILL.md | head -1) && \
	if [ "$$V" != "$$PV" ] || [ "$$V" != "$$SV" ]; then \
	  echo "VERSION DRIFT: VERSION=$$V plugin.json=$$PV SKILL.md=$$SV"; exit 1; \
	fi; \
	echo "version: $$V consistent across VERSION, plugin.json, SKILL.md."

release: version-check package
	@VERSION=$$(cat VERSION) && \
	git tag -a "v$$VERSION" -m "Release v$$VERSION" && \
	git push origin main && \
	git push origin "v$$VERSION" && \
	gh release create "v$$VERSION" $(ZIP_NAME) --title "v$$VERSION" --generate-notes && \
	echo "Released v$$VERSION"

vendor-jetcite:
	@test -d $(JETCITE_SRC) || (echo "FAIL: jetcite source not found at $(JETCITE_SRC)" && exit 1)
	rm -rf $(JETCITE_DEST)
	cp -r $(JETCITE_SRC) $(JETCITE_DEST)
	find $(JETCITE_DEST) -type d -name __pycache__ -exec rm -rf {} +  2>/dev/null || true
	@echo "Vendored jetcite from $(JETCITE_SRC)"

vendor-splitmarks:
	@test -f $(SPLITMARKS_SRC) || (echo "FAIL: splitmarks source not found at $(SPLITMARKS_SRC)" && exit 1)
	cp $(SPLITMARKS_SRC) $(SPLITMARKS_DEST)
	@echo "Vendored splitmarks from $(SPLITMARKS_SRC)"

# The ND Supreme Court's Redbook supplement. Canonical copy lives in the jetcite
# repo so jetmemo, jetredline, and jetrehearing cite one identical rule set.
vendor-citestyle:
	@test -f $(CITESTYLE_SRC) || (echo "FAIL: citation-style source not found at $(CITESTYLE_SRC)" && exit 1)
	cp $(CITESTYLE_SRC) $(CITESTYLE_DEST)
	@echo "Vendored nd-citation-style.md from $(CITESTYLE_SRC)"

# Fail if a vendored copy has drifted from its canonical source repo.
# Tolerant of canonical being absent (e.g. on an install-only machine).
drift-check:
	@if [ -f $(SPLITMARKS_SRC) ]; then \
	  cmp -s $(SPLITMARKS_SRC) $(SPLITMARKS_DEST) || { echo "DRIFT: $(SPLITMARKS_DEST) differs from canonical $(SPLITMARKS_SRC) — run 'make vendor-splitmarks'"; exit 1; }; \
	  echo "splitmarks: in sync with canonical."; \
	else \
	  echo "splitmarks: canonical repo not present ($(SPLITMARKS_SRC)); skipping drift check."; \
	fi
	@if [ -f $(CITESTYLE_SRC) ]; then \
	  cmp -s $(CITESTYLE_SRC) $(CITESTYLE_DEST) || { echo "DRIFT: $(CITESTYLE_DEST) differs from canonical $(CITESTYLE_SRC) — run 'make vendor-citestyle'"; exit 1; }; \
	  echo "nd-citation-style: in sync with canonical."; \
	else \
	  echo "nd-citation-style: canonical repo not present ($(CITESTYLE_SRC)); skipping drift check."; \
	fi

clean:
	rm -f $(SKILL_NAME)-skill*.zip

install:
	python3 install.py

test: drift-check version-check
	@echo "Validating skill structure..."
	@test -f skill/SKILL.md || (echo "FAIL: skill/SKILL.md missing" && exit 1)
	@test -d skill/references || (echo "FAIL: skill/references/ missing" && exit 1)
	@test -d skill/scripts || (echo "FAIL: skill/scripts/ missing" && exit 1)
	@test -f skill/scripts/splitmarks.py || (echo "FAIL: skill/scripts/splitmarks.py missing" && exit 1)
	@test -d skill/lib/jetcite || (echo "FAIL: skill/lib/jetcite/ missing — run 'make vendor-jetcite'" && exit 1)
	@test -f install.py || (echo "FAIL: install.py missing" && exit 1)
	@test -f README.md || (echo "FAIL: README.md missing" && exit 1)
	@test -f VERSION || (echo "FAIL: VERSION missing" && exit 1)
	@if [ -f test-data/check_page_break_pipeline.py ]; then \
	  python3 test-data/check_page_break_pipeline.py; \
	else \
	  echo "SKIP: page-break pipeline check (test-data/ not present)"; \
	fi
	@echo "All checks passed."
