from pathlib import Path

import pytest
import yaml

from src.config import load_config, AppConfig


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_config_minimal(tmp_path):
    config_dir = tmp_path / "configs"
    write_yaml(config_dir / "schedule.yaml", {
        "schedule": {"enabled": False, "mode": "weekly", "day": "sunday", "time": "09:00", "timezone": "UTC"},
        "window": {"daily_days": 3, "weekly_days": 14, "monthly_days": 45},
        "limits": {"max_candidates_per_source": 10, "max_total_candidates": 30, "max_runtime_minutes": 5},
    })
    write_yaml(config_dir / "sources.yaml", {
        "sources": {
            "crossref": {"enabled": True, "queries": [{"name": "q1", "query": "x"}], "max_results": 10},
            "arxiv": {"enabled": True, "categories": ["eess.SY"], "queries": [{"name": "q1", "query": "x"}], "max_results": 10},
        }
    })
    profile_dir = config_dir / "profiles" / "dtp-pmsm"
    write_yaml(profile_dir / "research_profile.yaml", {
        "research_profile": {
            "name": "X", "slug": "dtp-pmsm", "field": "f",
            "core_topics": [], "reject_topics": [],
            "rule_filter": {"require_year_after": 2018, "require_abstract": True, "blacklist_keywords": []},
        }
    })

    cfg = load_config(config_dir=config_dir, profile="dtp-pmsm")
    assert isinstance(cfg, AppConfig)
    assert cfg.profile.slug == "dtp-pmsm"
    assert cfg.sources.crossref.enabled is True


def test_load_config_missing_profile(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(config_dir=tmp_path / "nonexistent", profile="nope")
