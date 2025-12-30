"""Heuristics for guarding against non-eltariff content and results."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.rise_schema import TariffsResponse


@dataclass(frozen=True)
class TariffGuardResult:
    """Result of a tariff guard check."""

    ok: bool
    reason: str | None = None


KEYWORDS = {
    "elnät",
    "elnäts",
    "elnätsbolag",
    "elnätstariff",
    "elnätstariffer",
    "nätavgift",
    "nätavgifter",
    "överföringsavgift",
    "överföringsavgifter",
    "tariff",
    "tariffer",
    "effekt",
    "effektavgift",
    "effektavgifter",
    "abonnemang",
    "säkring",
    "förbrukning",
    "energipris",
    "energiavgift",
    "kwh",
    "kw",
    "kvar",
    "öre",
    "kr/kwh",
    "kr/kw",
    "rise",
    "elnätet",
}

STRONG_KEYWORDS = {
    "elnät",
    "elnätstariff",
    "nätavgift",
    "överföringsavgift",
    "effektavgift",
    "kwh",
    "kw",
    "kr/kwh",
    "kr/kw",
    "tariff",
}


def _keyword_hits(text: str) -> set[str]:
    lowered = text.lower()
    return {keyword for keyword in KEYWORDS if keyword in lowered}


def check_el_tariff_text(text: str) -> TariffGuardResult:
    """Check whether text looks like elnäts-/tariffinnehåll."""
    hits = _keyword_hits(text)
    strong_hit = any(keyword in hits for keyword in STRONG_KEYWORDS)

    if strong_hit and len(hits) >= 2:
        return TariffGuardResult(ok=True)

    return TariffGuardResult(
        ok=False,
        reason=(
            "Innehållet verkar inte beskriva en elnäts-/effekttariff. "
            "Skicka endast elnätsbolagsdata (tariffer, nätavgifter, kWh/kW-priser)."
        ),
    )


def check_tariffs_response(tariffs: TariffsResponse) -> TariffGuardResult:
    """Check that parsed tariffs look like elnätsdata."""
    if not tariffs.tariffs:
        return TariffGuardResult(
            ok=False,
            reason="Resultatet saknar tariffer och kan därför inte sparas.",
        )

    for tariff in tariffs.tariffs:
        if not tariff.company_name or not tariff.company_name.strip():
            return TariffGuardResult(
                ok=False,
                reason="Resultatet saknar företagsnamn och kan därför inte sparas.",
            )

        component_count = 0
        for element in (tariff.fixed_price, tariff.energy_price, tariff.power_price):
            if element and element.components:
                component_count += len(element.components)

        if component_count == 0:
            return TariffGuardResult(
                ok=False,
                reason="Resultatet saknar prismoduler och kan därför inte sparas.",
            )

    return TariffGuardResult(ok=True)
