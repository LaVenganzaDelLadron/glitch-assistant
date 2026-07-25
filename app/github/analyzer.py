
class RepoAnalyzer:
    def analyze(self, repo: dict) -> dict:
        """Analyze a repository's file listing and produce statistics.

        Args:
            repo: A dict containing a ``files`` key with a list of file metadata.

        Returns:
            A dict with ``python`` file count, ``markdown`` file count,
            and ``missing_readme`` boolean.
        """
        files = repo["files"]

        results = {
            "python": 0,
            "markdown": 0,
            "missing_readme": True,
        }

        for file in files:
            name = file["name"]

            if name.endswith(".py"):
                results["python"] += 1
            elif name.endswith(".md"):
                results["markdown"] += 1

            if name.lower() == "readme.md":
                results["missing_readme"] = False

        return results
