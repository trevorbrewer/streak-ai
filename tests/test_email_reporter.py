"""
tests/test_email_reporter.py
Tests for the email report module.
Mocks SendGrid so no real emails sent during CI.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.models import Hitter
from src import email_reporter


def make_hitter(name="Test Player", score=75, confidence="high") -> Hitter:
    h = Hitter(
        name=name,
        team="LAD",
        hand="R",
        avg=0.302,
        obp=0.390,
        slg=0.510,
        l7=0.330,
        woba=0.375,
        opp="SD",
        pitcher="Yu Darvish",
        phand="R",
        era=3.85,
        park="Petco Park",
        home_away="away",
        batting_order=3,
    )
    h.score      = score
    h.confidence = confidence
    h.reasoning  = "Test reasoning for this hitter today."
    h.key_factor = "Test key factor"
    return h


@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setitem(email_reporter.CONFIG, "sendgrid_api_key", "fake-sg-key")
    monkeypatch.setitem(email_reporter.CONFIG, "email_from", "test@example.com")
    monkeypatch.setitem(email_reporter.CONFIG, "email_recipients", ["recipient@example.com"])
    monkeypatch.setitem(email_reporter.CONFIG, "score_threshold", 65)
    monkeypatch.setitem(email_reporter.CONFIG, "streak_mode", "conservative")


def test_score_color_high():
    assert email_reporter._score_color(80) == "#00b87a"


def test_score_color_medium():
    assert email_reporter._score_color(65) == "#f5a623"


def test_score_color_low():
    assert email_reporter._score_color(45) == "#ff4f4f"


def test_score_color_boundary():
    assert email_reporter._score_color(75) == "#00b87a"
    assert email_reporter._score_color(74) == "#f5a623"
    assert email_reporter._score_color(60) == "#f5a623"
    assert email_reporter._score_color(59) == "#ff4f4f"


def test_confidence_badge_high():
    badge = email_reporter._confidence_badge("high")
    assert "HIGH" in badge
    assert "#00b87a" in badge


def test_confidence_badge_medium():
    badge = email_reporter._confidence_badge("medium")
    assert "MEDIUM" in badge
    assert "#f5a623" in badge


def test_confidence_badge_low():
    badge = email_reporter._confidence_badge("low")
    assert "LOW" in badge
    assert "#ff4f4f" in badge


def test_build_html_email_contains_hitter(mock_config):
    hitters = [make_hitter("Freddie Freeman", score=78)]
    html = email_reporter.build_html_email(hitters)
    assert "Freddie Freeman" in html
    assert "78" in html
    assert "LAD" in html


def test_build_html_email_contains_matchup(mock_config):
    hitters = [make_hitter(score=75)]
    html = email_reporter.build_html_email(hitters)
    assert "Yu Darvish" in html
    assert "Petco Park" in html
    assert "3.85" in html


def test_build_html_email_contains_reasoning(mock_config):
    hitters = [make_hitter(score=75)]
    html = email_reporter.build_html_email(hitters)
    assert "Test reasoning" in html
    assert "Test key factor" in html


def test_build_html_email_filters_by_threshold(mock_config):
    hitters = [
        make_hitter("Player A", score=80),
        make_hitter("Player B", score=40),
    ]
    html = email_reporter.build_html_email(hitters)
    assert "Player A" in html
    assert "Player B" in html
    # Player B should be in honorable mentions not main picks
    assert "Below Threshold" in html


def test_build_html_email_no_picks(mock_config):
    hitters = [make_hitter(score=30)]
    html = email_reporter.build_html_email(hitters)
    assert "No hitters above threshold" in html


def test_build_html_email_summary_stats(mock_config):
    hitters = [
        make_hitter("Player A", score=80),
        make_hitter("Player B", score=70),
        make_hitter("Player C", score=50),
    ]
    html = email_reporter.build_html_email(hitters)
    assert "STREAK" in html
    assert "3" in html  # 3 hitters scored


def test_build_text_email_contains_hitter(mock_config):
    hitters = [make_hitter("Freddie Freeman", score=78)]
    text = email_reporter.build_text_email(hitters)
    assert "Freddie Freeman" in text
    assert "78/100" in text


def test_build_text_email_no_picks(mock_config):
    hitters = [make_hitter(score=30)]
    text = email_reporter.build_text_email(hitters)
    assert "No picks above threshold" in text


def test_build_text_email_structure(mock_config):
    hitters = [make_hitter(score=75)]
    text = email_reporter.build_text_email(hitters)
    assert "STREAK·AI" in text
    assert "Daily Picks Report" in text
    assert "Not affiliated with ESPN" in text


def test_send_picks_email_no_api_key(monkeypatch, mock_config):
    monkeypatch.setitem(email_reporter.CONFIG, "sendgrid_api_key", "")
    hitters = [make_hitter(score=75)]
    result = email_reporter.send_picks_email(hitters)
    assert result is False


def test_send_picks_email_no_recipients(monkeypatch, mock_config):
    monkeypatch.setitem(email_reporter.CONFIG, "email_recipients", [])
    hitters = [make_hitter(score=75)]
    result = email_reporter.send_picks_email(hitters)
    assert result is False


def test_send_picks_email_success(mock_config, monkeypatch):
    monkeypatch.setattr(email_reporter, "SENDGRID_AVAILABLE", True)

    mock_response = MagicMock()
    mock_response.status_code = 202

    mock_sg = MagicMock()
    mock_sg.client.mail.send.post.return_value = mock_response

    with patch("src.email_reporter.sendgrid.SendGridAPIClient",
               return_value=mock_sg):
        hitters = [make_hitter(score=75)]
        result = email_reporter.send_picks_email(hitters)

    assert result is True
    assert mock_sg.client.mail.send.post.called


def test_send_picks_email_failure(mock_config, monkeypatch):
    monkeypatch.setattr(email_reporter, "SENDGRID_AVAILABLE", True)

    mock_sg = MagicMock()
    mock_sg.client.mail.send.post.side_effect = Exception("Network error")

    with patch("src.email_reporter.sendgrid.SendGridAPIClient",
               return_value=mock_sg):
        hitters = [make_hitter(score=75)]
        result = email_reporter.send_picks_email(hitters)

    assert result is False


def test_send_picks_email_subject_with_picks(mock_config, monkeypatch):
    monkeypatch.setattr(email_reporter, "SENDGRID_AVAILABLE", True)

    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_sg = MagicMock()
    mock_sg.client.mail.send.post.return_value = mock_response

    with patch("src.email_reporter.sendgrid.SendGridAPIClient",
               return_value=mock_sg):
        hitters = [make_hitter("Freddie Freeman", score=78)]
        email_reporter.send_picks_email(hitters)

    call_args = mock_sg.client.mail.send.post.call_args
    request_body = call_args[1]["request_body"]
    assert "Freddie Freeman" in str(request_body)


def test_preview_email_creates_file(tmp_path, mock_config):
    hitters = [make_hitter(score=75)]
    output = str(tmp_path / "test_preview.html")
    email_reporter.preview_email(hitters, output_path=output)
    assert (tmp_path / "test_preview.html").exists()
    content = (tmp_path / "test_preview.html").read_text()
    assert "STREAK" in content
