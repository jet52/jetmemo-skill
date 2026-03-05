SKILL_NAME := bench-memo
ZIP_NAME := $(SKILL_NAME)-skill.zip

.PHONY: package clean install test release

package: clean
	zip -r $(ZIP_NAME) skill/ install.sh README.md VERSION \
		-x "skill/.venv/*" "skill/node_modules/*" "skill/package-lock.json" "skill/__pycache__/*"

release:
	@VERSION=$$(cat VERSION) && \
	git tag -a "v$$VERSION" -m "Release v$$VERSION" && \
	echo "Tagged v$$VERSION" && \
	echo "Push with: git push origin v$$VERSION"

clean:
	rm -f $(ZIP_NAME)

install:
	bash install.sh

test:
	@echo "Validating skill structure..."
	@test -f skill/SKILL.md || (echo "FAIL: skill/SKILL.md missing" && exit 1)
	@test -d skill/references || (echo "FAIL: skill/references/ missing" && exit 1)
	@test -d skill/scripts || (echo "FAIL: skill/scripts/ missing" && exit 1)
	@test -f skill/scripts/splitmarks.py || (echo "FAIL: skill/scripts/splitmarks.py missing" && exit 1)
	@test -f install.sh || (echo "FAIL: install.sh missing" && exit 1)
	@test -f README.md || (echo "FAIL: README.md missing" && exit 1)
	@test -f VERSION || (echo "FAIL: VERSION missing" && exit 1)
	@echo "All checks passed."
