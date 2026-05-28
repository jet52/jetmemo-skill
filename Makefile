SKILL_NAME := jetmemo
VERSION := $(shell cat VERSION)
ZIP_NAME := $(SKILL_NAME)-skill-v$(VERSION).zip
JETCITE_SRC := ../jetcite/src/jetcite
JETCITE_DEST := skill/lib/jetcite

.PHONY: package clean install test release vendor-jetcite

package: clean
	mkdir -p $(SKILL_NAME)-skill
	cp -r skill/ install.py install.sh README.md VERSION $(SKILL_NAME)-skill/
	cd $(SKILL_NAME)-skill && rm -rf .venv node_modules package-lock.json __pycache__ TODO.md
	find $(SKILL_NAME)-skill -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	zip -r $(ZIP_NAME) $(SKILL_NAME)-skill/
	rm -rf $(SKILL_NAME)-skill

release: package
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

clean:
	rm -f $(SKILL_NAME)-skill*.zip

install:
	python3 install.py

test:
	@echo "Validating skill structure..."
	@test -f skill/SKILL.md || (echo "FAIL: skill/SKILL.md missing" && exit 1)
	@test -d skill/references || (echo "FAIL: skill/references/ missing" && exit 1)
	@test -d skill/scripts || (echo "FAIL: skill/scripts/ missing" && exit 1)
	@test -f skill/scripts/splitmarks.py || (echo "FAIL: skill/scripts/splitmarks.py missing" && exit 1)
	@test -d skill/lib/jetcite || (echo "FAIL: skill/lib/jetcite/ missing — run 'make vendor-jetcite'" && exit 1)
	@test -f install.py || (echo "FAIL: install.py missing" && exit 1)
	@test -f README.md || (echo "FAIL: README.md missing" && exit 1)
	@test -f VERSION || (echo "FAIL: VERSION missing" && exit 1)
	@echo "All checks passed."
