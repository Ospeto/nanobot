def test_scopes_include_calendar():
    from nanobot.game.google_api import SCOPES
    assert 'https://www.googleapis.com/auth/calendar' in SCOPES
