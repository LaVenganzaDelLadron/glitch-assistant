import requests

GITHUB_API_BASE = "https://api.github.com"


class GithubClient:

    def get_repository(self, repo: str) -> dict:
        """Get repository metadata from the GitHub API.

        Args:
            repo: Repository identifier in the format ``owner/repo``.

        Returns:
            Repository metadata as a dict.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def get_contents(self, repo: str) -> list[dict]:
        """Get the top-level file listing of a repository.

        Args:
            repo: Repository identifier in the format ``owner/repo``.

        Returns:
            List of file metadata dicts.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/contents"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
