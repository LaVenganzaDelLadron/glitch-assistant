"""GitHub module — repository handling (client, clone, scanner).

Note: RepoCloner and RepoScanner are now re-exported from the ``scanner`` module.
This file maintains backward compatibility.
"""

from app.github.client import GithubClient
from scanner.repo_cloner import RepoCloner, CloneError
from scanner.file_indexer import FileIndexer as RepoScanner

__all__ = [
    "GithubClient",
    "RepoCloner",
    "CloneError",
    "RepoScanner",
]

