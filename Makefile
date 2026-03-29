.PHONY: sync-skills check-skills

sync-skills:
	python3 scripts/sync_skills.py

check-skills:
	python3 scripts/sync_skills.py --check
