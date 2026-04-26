import random
from typing import Any

import database

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]

DEFAULT_SETTINGS = {
    "collectable_drop_base_chance": 0.015,
    "collectable_drop_pity_step": 0.0004,
    "collectable_drop_pity_cap": 0.03,
    "collectable_msg_cooldown_seconds": 45,
    "craft_diamond_cost": 10,
    "wishlist_bonus_natural": 0.18,
    "wishlist_bonus_craft": 0.10,
    "rarity_weight_common": 60.0,
    "rarity_weight_uncommon": 25.0,
    "rarity_weight_rare": 10.0,
    "rarity_weight_epic": 4.0,
    "rarity_weight_legendary": 1.0,
    "scrap_value_common": 1,
    "scrap_value_uncommon": 2,
    "scrap_value_rare": 4,
    "scrap_value_epic": 8,
    "scrap_value_legendary": 16,
    "wishlist_max_items": 5,
}


def _get_float_setting(key: str) -> float:
    raw = database.get_setting(key, str(DEFAULT_SETTINGS[key]))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(DEFAULT_SETTINGS[key])


def _get_int_setting(key: str) -> int:
    raw = database.get_setting(key, str(DEFAULT_SETTINGS[key]))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS[key])


def get_drop_config() -> dict[str, float | int]:
    return {
        "base_chance": _get_float_setting("collectable_drop_base_chance"),
        "pity_step": _get_float_setting("collectable_drop_pity_step"),
        "pity_cap": _get_float_setting("collectable_drop_pity_cap"),
        "cooldown_seconds": _get_int_setting("collectable_msg_cooldown_seconds"),
    }


def get_craft_cost() -> int:
    return _get_int_setting("craft_diamond_cost")


def get_wishlist_bonus(source: str) -> float:
    if source == "natural":
        return _get_float_setting("wishlist_bonus_natural")
    return _get_float_setting("wishlist_bonus_craft")


def get_wishlist_cap() -> int:
    return _get_int_setting("wishlist_max_items")


def get_scrap_value(rarity: str) -> int:
    key = f"scrap_value_{rarity.lower()}"
    return _get_int_setting(key) if key in DEFAULT_SETTINGS else 1


def choose_rarity() -> str | None:
    weighted_rarities: list[tuple[str, float]] = []
    for rarity in RARITY_ORDER:
        weight = _get_float_setting(f"rarity_weight_{rarity}")
        if weight > 0:
            weighted_rarities.append((rarity, weight))
    if not weighted_rarities:
        return None
    rarities = [r for r, _ in weighted_rarities]
    weights = [w for _, w in weighted_rarities]
    return random.choices(rarities, weights=weights, k=1)[0]


def choose_collectable_with_wishlist_bias(
    user_id: int, rarity: str, source: str
) -> tuple[Any, ...] | None:
    pool = database.get_collectables_by_rarity(rarity)
    if not pool:
        return None

    wishlist_ids = {item[0] for item in database.get_user_wishlist(user_id)}
    wished_pool = [item for item in pool if item[0] in wishlist_ids]

    if wished_pool:
        bonus = max(0.0, min(1.0, get_wishlist_bonus(source)))
        if random.random() < bonus:
            return random.choice(wished_pool)

    return random.choice(pool)
