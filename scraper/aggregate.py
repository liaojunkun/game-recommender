#!/usr/bin/env python3
"""数据聚合模块：合并 3DM 和 ali213 游戏数据，统一格式、去重、排序。"""

import json
import os
import re
from pathlib import Path

from . import config

PROJECT_ROOT = config.PROJECT_ROOT


def normalize_chinese_date(date_str: str) -> str:
    """将中文日期格式转换为 YYYY-MM-DD 格式。
    例如: '2026年5月12日' -> '2026-05-12'
          '2026年2月27日 ( PC )' -> '2026-02-27'
          '' -> ''
    """
    if not date_str or not date_str.strip():
        return ""
    date_str = date_str.strip()
    # 匹配 "YYYY年M月D日..." 格式
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # 匹配 "YYYY/MM/DD" 格式
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def parse_sortable_date(date_str: str) -> str:
    """返回可排序的日期字符串，无法解析的返回空字符串。"""
    normalized = normalize_chinese_date(date_str)
    if normalized:
        return normalized
    return ""


def aggregate_3dm(raw_list: list[dict]) -> list[dict]:
    """将 3DM 原始数据转换为统一格式。"""
    result = []
    for item in raw_list:
        # 优先使用 tags 数组作为 type
        tags = item.get("tags", [])
        type_str = ", ".join(tags) if tags else ""

        # 如果 tags 为空，尝试从 description 中提取"类型：xxx |"
        if not type_str:
            desc = item.get("description", "")
            m = re.match(r"类型：([^|]+)", desc)
            if m:
                type_str = m.group(1).strip()

        # 保留原始来源分类（如"近期新作"、"3DM-排行榜"、"3DM-专题"）
        original_source = item.get("source", "3DM")

        result.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "image": item.get("image", ""),
            "description": item.get("description", ""),
            "source": original_source,
            "date": normalize_chinese_date(item.get("date", "")),
            "type": type_str,
            "platform": "3DM",
        })
    return result


def aggregate_ali213(raw_list: list[dict]) -> list[dict]:
    """将 ali213 原始数据转换为统一格式。"""
    result = []
    for item in raw_list:
        # 保留原始来源分类（如"ali213-期待榜"、"ali213-好评榜"等）
        original_source = item.get("source", "ali213")

        result.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "image": item.get("image", ""),
            "description": item.get("description", ""),
            "source": original_source,
            "date": normalize_chinese_date(item.get("date", "")),
            "type": item.get("type", ""),
            "platform": "ali213",
        })
    return result


def aggregate_gamer520(raw_list: list[dict]) -> list[dict]:
    """将 gamer520 原始数据转换为统一格式。"""
    result = []
    for item in raw_list:
        entry = {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "image": item.get("image", ""),
            "description": item.get("description", ""),
            "source": "GAMER520",
            "date": item.get("date", ""),
            "type": "",
            "platform": "GAMER520",
        }
        # 传递排名字段（rank_date 不需要，前端直接用 date 字段排序）
        for key in ["rank_hot", "rank_comment_count"]:
            if key in item:
                entry[key] = item[key]
        result.append(entry)
    return result


def deduplicate_by_url(games: list[dict]) -> list[dict]:
    """基于 URL 去重（忽略大小写），优先保留有更多信息的记录。"""
    seen = {}  # url_lower -> index in result list
    result = []

    for game in games:
        url_lower = game["url"].lower()
        if url_lower in seen:
            # 去重：保留信息更丰富（非空字段更多）的记录
            existing = result[seen[url_lower]]
            new_score = sum(1 for v in game.values() if v and str(v).strip())
            existing_score = sum(1 for v in existing.values() if v and str(v).strip())
            if new_score > existing_score:
                result[seen[url_lower]] = game
        else:
            seen[url_lower] = len(result)
            result.append(game)

    return result


def sort_by_date(games: list[dict]) -> list[dict]:
    """按日期降序排序（有日期的排前面，无日期的排后面）。"""
    def sort_key(game):
        date_str = parse_sortable_date(game.get("date", ""))
        if date_str:
            # 有日期：用日期作为排序 key，降序
            return (0, date_str)
        else:
            # 无日期：排在后面
            return (1, "")

    return sorted(games, key=sort_key, reverse=True)


def main():
    data_dir = config.DATA_DIR
    out_file = config.AGGREGATE_CONFIG["output_file"]

    # 读取源数据
    with open(data_dir / "3dm_games.json", encoding="utf-8") as f:
        raw_3dm = json.load(f)
    with open(data_dir / "ali213_games.json", encoding="utf-8") as f:
        raw_ali213 = json.load(f)

    print(f"读取 3DM 数据: {len(raw_3dm)} 条")
    print(f"读取 ali213 数据: {len(raw_ali213)} 条")

    # 统一格式
    games_3dm = aggregate_3dm(raw_3dm)
    games_ali213 = aggregate_ali213(raw_ali213)

    # 合并
    all_games = games_3dm + games_ali213
    print(f"合并后: {len(all_games)} 条")

    # 去重
    unique_games = deduplicate_by_url(all_games)
    print(f"去重后: {len(unique_games)} 条")

    # 按日期排序
    sorted_games = sort_by_date(unique_games)

    # 输出
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(sorted_games, f, ensure_ascii=False, indent=2)

    print(f"输出到: {out_file}")

    # 统计信息
    sources = {}
    for g in sorted_games:
        src = g["source"]
        sources[src] = sources.get(src, 0) + 1
    print(f"数据源分布: {sources}")

    with_date = sum(1 for g in sorted_games if g["date"])
    without_date = len(sorted_games) - with_date
    print(f"有日期: {with_date}, 无日期: {without_date}")


if __name__ == "__main__":
    main()
