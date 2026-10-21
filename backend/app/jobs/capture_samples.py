"""Recolhe amostras anonimizadas de um board (work-item A2) e valida-as contra os DTOs.

Uso: python -m app.jobs.capture_samples [--board 96] [--out DIR] [--cards 20]

Grava JSON anonimizados (títulos, descrições, comentários e identidades substituídos)
e imprime: limites da API, cabeçalhos de rate limit, paginação e chaves reais de
`transitions`/`block_times`/`lead_time_per_column` (não documentadas no OpenAPI).
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.integrations.businessmap import CARD_FIELDS, BusinessmapClient
from app.models.businessmap import BmCard

TEXT_KEYS = {"title", "description", "comment", "text", "content", "last_comment", "discard_comment"}
IDENTITY_KEYS = {"username", "realname", "email", "avatar"}


def anonymize(value: Any, counter: dict[str, int] | None = None, key: str | None = None) -> Any:
    counter = counter if counter is not None else {}
    if isinstance(value, dict):
        return {k: anonymize(v, counter, k) for k, v in value.items()}
    if isinstance(value, list):
        return [anonymize(v, counter, key) for v in value]
    if isinstance(value, str) and key in TEXT_KEYS | IDENTITY_KEYS | {"custom_id"}:
        counter[key] = counter.get(key, 0) + 1
        return f"<{key}-{counter[key]}>"
    return value


def _keys(cards: list[dict[str, Any]], field: str) -> list[str]:
    keys: set[str] = set()
    for card in cards:
        items = card.get(field)
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict):
                keys.update(item)
    return sorted(keys)


async def capture(board_id: int, out: Path, max_cards: int) -> dict[str, Any]:
    settings = get_settings()
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"board_id": board_id}
    async with BusinessmapClient.from_settings(settings) as client:
        samples = {
            "boards": await client.get_boards([board_id]),
            "current_structure": await client.get_board_structure(board_id),
            "cycle_time_columns": await client.get_cycle_time_columns(board_id),
            "api_limits": await client.get_api_limits(),
            "card_types": await client.get_card_types(),
        }
        expand = ["transitions", "block_times", "lead_time_per_column", "co_owner_ids", "tag_ids"]
        page = await client.list_cards(board_id, per_page=max_cards, fields=CARD_FIELDS, expand=expand)
        archived = await client.list_cards(board_id, state="archived", per_page=min(max_cards, 5), fields=CARD_FIELDS, expand=expand)
        samples["cards_active"] = page.cards
        samples["cards_archived"] = archived.cards
        report["pagination"] = {"active_pages": page.all_pages, "per_page": max_cards, "archived_pages": archived.all_pages}
        report["rate_limit_remaining"] = vars(client.rate_limit)
        report["requests"] = client.request_count

    errors = []
    for raw in samples["cards_active"] + samples["cards_archived"]:
        try:
            BmCard.model_validate(raw)
        except ValidationError as exc:
            errors.append({"card": raw.get("card_id"), "errors": exc.errors(include_url=False)})
    all_cards = samples["cards_active"] + samples["cards_archived"]
    report["dto_errors"] = errors
    report["api_limits"] = samples["api_limits"]
    report["expanded_keys"] = {f: _keys(all_cards, f) for f in ("transitions", "block_times", "lead_time_per_column")}

    for name, data in samples.items():
        (out / f"{name}_{board_id}.json").write_text(
            json.dumps(anonymize(data), indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
        )
    (out / f"report_{board_id}.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=int, default=settings.businessmap_default_board_id)
    parser.add_argument("--out", type=Path, default=Path("samples"))
    parser.add_argument("--cards", type=int, default=20)
    args = parser.parse_args()
    configure_logging(settings)
    report = asyncio.run(capture(args.board, args.out, args.cards))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
