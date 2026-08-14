SKILL_NAME := jetmemo
VERSION := $(shell cat VERSION)
ZIP_NAME := $(SKILL_NAME)-skill-v$(VERSION).zip
PLUGIN_ZIP := $(SKILL_NAME)-plugin-v$(VERSION).zip
JETCITE_SRC := ../jetcite/src/jetcite
JETCITE_DEST := skill/lib/jetcite
SPLITMARKS_SRC := ../splitmarks/splitmarks.py
SPLITMARKS_DEST := skill/scripts/splitmarks.py
TEXTQUALITY_SRC := ../splitmarks/textquality.py
TEXTQUALITY_DEST := skill/scripts/textquality.py
CITESTYLE_SRC := ../jetcite/reference/nd-citation-style.md
CITESTYLE_DEST := skill/references/nd-citation-style.md

.PHONY: package package-plugin package-all clean install test release check-assets vendor-jetcite vendor-splitmarks vendor-textquality vendor-citestyle drift-check version-check
.PHONY: build-skill build-plugin

# Public targets clean first, then delegate. package-all cleans once so the
# two build recipes cannot clobber each other's output.
#
# The clean matters: `zip -r` ADDS to an existing archive rather than replacing
# it, so building over a stale zip keeps every file any earlier build put
# there. jetbriefcheck shipped exactly that bug — its archive had quietly
# accumulated repo-root files that were never part of the skill.
package: clean build-skill
package-plugin: clean build-plugin
package-all: clean build-skill build-plugin

# Standalone installer bundle: jetmemo-skill/ at the archive root, carrying the
# skill tree plus install.py/install.sh for a manual drop into ~/.claude/skills/.
build-skill:
	mkdir -p $(SKILL_NAME)-skill
	cp -r skill/ install.py install.sh README.md VERSION $(SKILL_NAME)-skill/
	cd $(SKILL_NAME)-skill && rm -rf .venv node_modules package-lock.json __pycache__ TODO.md
	find $(SKILL_NAME)-skill -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	zip -r $(ZIP_NAME) $(SKILL_NAME)-skill/
	rm -rf $(SKILL_NAME)-skill

# Plugin archive for Cowork ("Customize -> Plugins") and marketplace upload.
#
# Shape is dictated by the manifest, not by taste: plugin.json declares
# "skills": "./skill", so the archive must carry .claude-plugin/plugin.json at
# its root and the skill tree at exactly that relative path. The installer
# bundle above is NOT interchangeable — it nests everything under
# jetmemo-skill/ and ships no manifest, so Cowork reads it as a bare skill.
build-plugin:
	zip -r $(PLUGIN_ZIP) .claude-plugin/plugin.json skill/ \
		-x "skill/.venv/*" "skill/node_modules/*" \
		   "skill/package-lock.json" "*/__pycache__/*" "*.pyc"

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

release: version-check package-all
	@VERSION=$$(cat VERSION) && \
	git tag -a "v$$VERSION" -m "Release v$$VERSION" && \
	git push origin main && \
	git push origin "v$$VERSION" && \
	gh release create "v$$VERSION" $(PLUGIN_ZIP) $(ZIP_NAME) --title "v$$VERSION" --generate-notes && \
	$(MAKE) --no-print-directory check-assets TAG="v$$VERSION" ASSETS="$(PLUGIN_ZIP) $(ZIP_NAME)" && \
	echo "Released v$$VERSION"

# `gh release create` has been observed to exit 0 after silently skipping an
# asset: jetredline v4.19.1 was handed three zips, attached two, and reported
# success, so `make release` announced a release that was missing the file
# manual installers download. Nothing in the toolchain caught it. This asserts
# every expected asset actually landed, retries once, then fails hard — a
# release that cannot prove its assets is a failed release.
check-assets:
	@test -n "$(TAG)" || { echo "check-assets: TAG not set"; exit 1; }
	@for f in $(ASSETS); do \
	  if ! gh release view "$(TAG)" --json assets --jq '.assets[].name' | grep -qx "$$f"; then \
	    echo "MISSING: $$f did not attach to $(TAG); retrying upload"; \
	    gh release upload "$(TAG)" "$$f" --clobber || true; \
	  fi; \
	done
	@missing=0; \
	for f in $(ASSETS); do \
	  gh release view "$(TAG)" --json assets --jq '.assets[].name' | grep -qx "$$f" || \
	    { echo "FAIL: $$f is still not attached to $(TAG)"; missing=1; }; \
	done; \
	[ $$missing -eq 0 ] || exit 1; \
	echo "assets verified on $(TAG): $(ASSETS)"

vendor-jetcite:
	@test -d $(JETCITE_SRC) || (echo "FAIL: jetcite source not found at $(JETCITE_SRC)" && exit 1)
	rm -rf $(JETCITE_DEST)
	cp -r $(JETCITE_SRC) $(JETCITE_DEST)
	find $(JETCITE_DEST) -type d -name __pycache__ -exec rm -rf {} +  2>/dev/null || true
	@echo "Vendored jetcite from $(JETCITE_SRC)"

# Depends on vendor-textquality because splitmarks imports textquality inside a
# try/except: vendoring the script without the module leaves --check-text
# silently back on the old density-only behaviour, which is the exact failure
# this pairing exists to prevent. The two always move together.
vendor-splitmarks: vendor-textquality
	@test -f $(SPLITMARKS_SRC) || (echo "FAIL: splitmarks source not found at $(SPLITMARKS_SRC)" && exit 1)
	cp $(SPLITMARKS_SRC) $(SPLITMARKS_DEST)
	@echo "Vendored splitmarks from $(SPLITMARKS_SRC)"

# Text-layer quality scorer that splitmarks --check-text consults to tell a
# corrupt text layer (dense but garbage) from a missing one. Canonical copy
# lives in the splitmarks repo beside the script that imports it; it must land
# in the same directory as splitmarks.py for that import to resolve.
vendor-textquality:
	@test -f $(TEXTQUALITY_SRC) || (echo "FAIL: textquality source not found at $(TEXTQUALITY_SRC)" && exit 1)
	cp $(TEXTQUALITY_SRC) $(TEXTQUALITY_DEST)
	@echo "Vendored textquality from $(TEXTQUALITY_SRC)"

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
	@if [ -f $(TEXTQUALITY_SRC) ]; then \
	  cmp -s $(TEXTQUALITY_SRC) $(TEXTQUALITY_DEST) || { echo "DRIFT: $(TEXTQUALITY_DEST) differs from canonical $(TEXTQUALITY_SRC) — run 'make vendor-textquality'"; exit 1; }; \
	  echo "textquality: in sync with canonical."; \
	else \
	  echo "textquality: canonical repo not present ($(TEXTQUALITY_SRC)); skipping drift check."; \
	fi
	@if [ -f $(CITESTYLE_SRC) ]; then \
	  cmp -s $(CITESTYLE_SRC) $(CITESTYLE_DEST) || { echo "DRIFT: $(CITESTYLE_DEST) differs from canonical $(CITESTYLE_SRC) — run 'make vendor-citestyle'"; exit 1; }; \
	  echo "nd-citation-style: in sync with canonical."; \
	else \
	  echo "nd-citation-style: canonical repo not present ($(CITESTYLE_SRC)); skipping drift check."; \
	fi

clean:
	rm -f $(SKILL_NAME)-skill*.zip $(SKILL_NAME)-plugin*.zip
	rm -rf $(SKILL_NAME)-skill

install:
	python3 install.py

test: drift-check version-check
	@echo "Validating skill structure..."
	@test -f skill/SKILL.md || (echo "FAIL: skill/SKILL.md missing" && exit 1)
	@test -d skill/references || (echo "FAIL: skill/references/ missing" && exit 1)
	@test -d skill/scripts || (echo "FAIL: skill/scripts/ missing" && exit 1)
	@test -f skill/scripts/splitmarks.py || (echo "FAIL: skill/scripts/splitmarks.py missing" && exit 1)
	@test -f skill/scripts/textquality.py || (echo "FAIL: skill/scripts/textquality.py missing — run 'make vendor-textquality'" && exit 1)
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
