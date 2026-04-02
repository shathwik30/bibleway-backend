from __future__ import annotations

from config.settings.prod import _build_csrf_trusted_origins


class TestBuildCsrfTrustedOrigins:
    def test_includes_configured_https_origins(self):
        origins = _build_csrf_trusted_origins([
            "https://bibleway.io",
            "https://api.bibleway.io",
        ])
        assert "https://bibleway.io" in origins
        assert "https://api.bibleway.io" in origins
        assert "https://*.up.railway.app" in origins

    def test_ignores_invalid_origins_and_deduplicates(self):
        origins = _build_csrf_trusted_origins([
            "https://bibleway.io",
            "https://bibleway.io",
            "bibleway.io",
            "",
        ])
        assert origins.count("https://bibleway.io") == 1
        assert "bibleway.io" not in origins
