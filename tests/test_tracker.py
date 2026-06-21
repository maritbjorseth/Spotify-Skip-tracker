"""
Tester for skip-deteksjonslogikken i tracker.py.

is_skip() er en ren funksjon uten bivirkninger, noe som gjør det trivielt
å dekke alle grensetilfeller uten å trenge en database eller nettverkstilgang.
"""

import pytest

from spotify_skip_tracker.tracker import is_skip
from spotify_skip_tracker.config import SKIP_THRESHOLD, MIN_REMAINING_MS


# ---------------------------------------------------------------------------
# Grunnleggende skip-deteksjon
# ---------------------------------------------------------------------------

class TestIsSkip:
    def test_klart_skip(self):
        """Sang skippet tidlig med mye igjen → skip."""
        assert is_skip(ratio=0.3, remaining_ms=180_000, shuffle_toggled=False, context_switched=False) is True

    def test_akkurat_paa_grensen(self):
        """ratio == SKIP_THRESHOLD er IKKE skip (krever ratio < threshold)."""
        assert is_skip(ratio=SKIP_THRESHOLD, remaining_ms=MIN_REMAINING_MS, shuffle_toggled=False, context_switched=False) is False

    def test_rett_under_grensen(self):
        """ratio like under threshold og akkurat nok remaining → skip."""
        assert is_skip(ratio=SKIP_THRESHOLD - 0.001, remaining_ms=MIN_REMAINING_MS, shuffle_toggled=False, context_switched=False) is True

    def test_fullfort_sang(self):
        """Sang spilt ferdig (ratio >= 0.9) → ikke skip."""
        assert is_skip(ratio=0.95, remaining_ms=5_000, shuffle_toggled=False, context_switched=False) is False

    def test_naturlig_avslutning_nar_ratio_er_hoy(self):
        """Ratio over threshold → ikke skip, uavhengig av remaining."""
        assert is_skip(ratio=1.0, remaining_ms=0, shuffle_toggled=False, context_switched=False) is False

    # ---------------------------------------------------------------------------
    # Gjenværende tid
    # ---------------------------------------------------------------------------

    def test_for_lite_igjen_er_ikke_skip(self):
        """Sang avsluttet med < 30 s igjen (outro) → ikke skip."""
        assert is_skip(ratio=0.5, remaining_ms=MIN_REMAINING_MS - 1, shuffle_toggled=False, context_switched=False) is False

    def test_akkurat_nok_igjen(self):
        """Nøyaktig MIN_REMAINING_MS igjen → skip (grensetilfelle)."""
        assert is_skip(ratio=0.5, remaining_ms=MIN_REMAINING_MS, shuffle_toggled=False, context_switched=False) is True

    def test_mye_igjen(self):
        """Mye igjen → skip."""
        assert is_skip(ratio=0.1, remaining_ms=300_000, shuffle_toggled=False, context_switched=False) is True

    # ---------------------------------------------------------------------------
    # Shuffle-bytte
    # ---------------------------------------------------------------------------

    def test_shuffle_toggled_er_ikke_skip(self):
        """Shuffle-bytte hopper til ny sang — skal ikke telle som skip."""
        assert is_skip(ratio=0.3, remaining_ms=180_000, shuffle_toggled=True, context_switched=False) is False

    def test_shuffle_toggled_med_naturlig_avslutning(self):
        """Shuffle-bytte ved høy ratio → heller ikke skip."""
        assert is_skip(ratio=0.95, remaining_ms=5_000, shuffle_toggled=True, context_switched=False) is False

    # ---------------------------------------------------------------------------
    # Kontekstbytte
    # ---------------------------------------------------------------------------

    def test_context_switched_er_ikke_skip(self):
        """Nytt album/spilleliste mid-sang → skal ikke telle som skip."""
        assert is_skip(ratio=0.3, remaining_ms=180_000, shuffle_toggled=False, context_switched=True) is False

    def test_begge_flagg_satt(self):
        """Både shuffle og kontekst byttet → definitivt ikke skip."""
        assert is_skip(ratio=0.1, remaining_ms=300_000, shuffle_toggled=True, context_switched=True) is False

    # ---------------------------------------------------------------------------
    # Kanttilfeller med ratio
    # ---------------------------------------------------------------------------

    def test_ratio_null(self):
        """Sporet byttes umiddelbart (ratio = 0) → skip."""
        assert is_skip(ratio=0.0, remaining_ms=MIN_REMAINING_MS, shuffle_toggled=False, context_switched=False) is True

    def test_ratio_litt_over_null(self):
        """Nesten ikke spilt i det hele tatt → skip."""
        assert is_skip(ratio=0.01, remaining_ms=MIN_REMAINING_MS + 1000, shuffle_toggled=False, context_switched=False) is True
