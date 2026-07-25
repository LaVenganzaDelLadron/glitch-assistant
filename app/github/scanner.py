
class GithubScanner:
    def __init__(self, client) -> None:
        self.client = client

    def scan(self, repo: str) -> dict:
        """Scan a repository and return its metadata and file listing.

        Args:
            repo: Repository identifier in the format ``owner/repo``.

        Returns:
            A dict with ``repo`` metadata and ``files`` contents.
        """
        repo_data = self.client.get_repository(repo)
        files = self.client.get_contents(repo)

        return {"repo": repo_data, "files": files}
