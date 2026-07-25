# Refactoring Plan - Repository Analysis System

## Phase 1: Fix Critical Bugs
- [x] 1a. Fix RepoCloner.clone() - wrap with @contextmanager
- [x] 1b. Fix tool_choice error - remove tool_choice="none" from groq.py

## Phase 2: Create New Module Structure
- [ ] 2a. Create scanner/ package with files
- [ ] 2b. Create security/ package with files
- [ ] 2c. Create metrics/ package with files

## Phase 3: Implement New Modules
- [ ] 3a. scanner/repo_cloner.py (moved from app/github/clone.py, fixed context manager)
- [ ] 3b. scanner/file_indexer.py (moved from app/github/scanner.py)
- [ ] 3c. scanner/language_detector.py
- [ ] 3d. scanner/dependency_detector.py
- [ ] 3e. security/security_scanner.py
- [ ] 3f. metrics/complexity.py
- [ ] 3g. metrics/documentation.py
- [ ] 3h. metrics/git_scanner.py
- [ ] 3i. analysis/prompt_builder.py
- [ ] 3j. analysis/report_builder.py

## Phase 4: Rewrite Core Pipeline
- [ ] 4a. Rewrite analysis/analyzer.py (Python owns all execution)
- [ ] 4b. Rewrite analysis/prompts.py (remove tool-calling instructions)
- [ ] 4c. Enhance terminal/command_runner.py with more commands

## Phase 5: Fix Intent Detection
- [ ] 5a. Update thinker.py with regex URL detection

## Phase 6: Clean Up Old Files
- [ ] 6a. Update all __init__.py files
- [ ] 6b. Remove/replace old files as needed

