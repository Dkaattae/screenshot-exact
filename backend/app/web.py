"""Serves the built frontend (a single-page app) next to the API."""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

SHELL = "_shell.html"


class SinglePageApp(StaticFiles):
    """Static files, falling back to the app shell for client-side routes like /wardrobe.

    Paths that look like files (/assets/x.js) still 404 when missing, so a bad asset link
    fails loudly instead of returning HTML.
    """

    def __init__(self, directory: str | Path) -> None:
        if not (Path(directory) / SHELL).is_file():
            raise RuntimeError(f"{directory} has no {SHELL}. Build the frontend with SPA_BUILD=1.")
        super().__init__(directory=directory, html=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in Path(path).name:
                raise
            return await super().get_response(SHELL, scope)
