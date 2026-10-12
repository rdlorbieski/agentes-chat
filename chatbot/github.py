"""Leitura, só leitura, dos repositórios de agentes no GitHub."""

import requests

from .campanhas import ler_campanha

API = "https://api.github.com"


class ErroGitHub(Exception):
    """Falha ao ler o GitHub, com uma mensagem que dá para mostrar na tela."""


class GitHub:
    def __init__(self, token, sessao=None):
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self.sessao.headers["Authorization"] = f"Bearer {token}"

    def _get(self, repo, caminho, **kwargs):
        resposta = self.sessao.get(f"{API}/repos/{repo}/{caminho}", timeout=30, **kwargs)
        if resposta.status_code in (401, 403, 404):
            raise ErroGitHub(
                f"O GitHub recusou a leitura de {repo} (HTTP {resposta.status_code}). "
                "Confira se o GITHUB_TOKEN tem acesso a esse repositório com Issues e "
                "Contents em Read-only."
            )
        resposta.raise_for_status()
        return resposta

    def campanhas(self, repo, limite=20):
        """Issues de prioridades, da mais nova para a mais antiga."""
        issues = self._get(
            repo,
            "issues",
            params={
                "labels": "prioridades",
                "state": "all",
                "per_page": limite,
                "sort": "created",
                "direction": "desc",
            },
        ).json()
        # A API de issues também devolve pull requests; eles não são campanhas.
        return [ler_campanha(i) for i in issues if "pull_request" not in i]

    def arquivo(self, repo, caminho):
        """Conteúdo de um arquivo de texto da branch padrão, ou "" se ele não existir."""
        try:
            return self._get(
                repo,
                f"contents/{caminho}",
                headers={"Accept": "application/vnd.github.raw+json"},
            ).text
        except ErroGitHub:
            return ""
