#!/usr/bin/env python3
"""
单机游戏推荐站 - 数据抓取入口

主入口脚本，负责解析命令行参数并调用 scraper 模块进行游戏数据抓取。

用法:
    python run_scraper.py                    # 抓取全部来源并聚合
    python run_scraper.py --source 3dm       # 只抓取 3DM
    python run_scraper.py --source ali213    # 只抓取游侠网
    python run_scraper.py --source all       # 抓取全部来源
    python run_scraper.py --delay 2          # 设置请求延迟
"""

import argparse
import os
import sys

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from scraper import scrape_3dm, scrape_ali213, scrape_gamer520, config
from scraper.aggregate import aggregate_3dm, aggregate_ali213, aggregate_gamer520, deduplicate_by_url, sort_by_date


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="单机游戏推荐站 - 数据抓取工具"
    )
    parser.add_argument(
        "--source",
        choices=["all", "3dm", "ali213", "gamer520"],
        default="all",
        help="指定抓取来源: all(全部), 3dm, ali213, gamer520 (默认: all)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(config.AGGREGATE_CONFIG["output_file"]),
        help="输出文件路径 (默认: data/games.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        help=f"请求间隔秒数，用于避免反爬 (默认: {config.REQUEST_DELAY})",
    )
    return parser.parse_args()


def scrape_and_save(source: str, output_file: str, delay: float) -> list:
    """
    抓取数据并聚合保存。

    Args:
        source: 数据来源
        output_file: 输出文件路径
        delay: 请求延迟

    Returns:
        聚合后的游戏列表
    """
    raw_3dm = []
    raw_ali213 = []
    raw_gamer520 = []

    if source in ("all", "3dm"):
        print("\n" + "=" * 50)
        print("[1/4] 抓取 3DM 数据...")
        print("=" * 50)
        raw_3dm = scrape_3dm.scrape_3dm(delay=delay)
        print(f"  -> 3DM 原始数据: {len(raw_3dm)} 条")

    if source in ("all", "ali213"):
        print("\n" + "=" * 50)
        print("[2/4] 抓取游侠网数据...")
        print("=" * 50)
        raw_ali213 = scrape_ali213.scrape_ali213(delay=delay)
        print(f"  -> 游侠网原始数据: {len(raw_ali213)} 条")

    if source in ("all", "gamer520"):
        print("\n" + "=" * 50)
        print("[3/4] 抓取 Gamer520 数据...")
        print("=" * 50)
        raw_gamer520 = scrape_gamer520.scrape_gamer520(delay=delay)
        print(f"  -> Gamer520 原始数据: {len(raw_gamer520)} 条")

    print("\n" + "=" * 50)
    print("[4/4] 数据聚合...")
    print("=" * 50)

    games_3dm = aggregate_3dm(raw_3dm)
    games_ali213 = aggregate_ali213(raw_ali213)
    games_gamer520 = aggregate_gamer520(raw_gamer520)

    # 合并、去重、排序
    all_games = games_3dm + games_ali213 + games_gamer520
    print(f"  -> 合并后: {len(all_games)} 条")

    unique_games = deduplicate_by_url(all_games)
    print(f"  -> 去重后: {len(unique_games)} 条")

    sorted_games = sort_by_date(unique_games)
    print(f"  -> 排序完成: {len(sorted_games)} 条")

    # 保存到指定路径
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        import json
        json.dump(sorted_games, f, ensure_ascii=False, indent=2)
    print(f"  -> 已保存到: {output_file}")

    return sorted_games


def main():
    """主函数"""
    args = parse_args()

    print("=" * 50)
    print("单机游戏推荐站 - 数据抓取工具")
    print("=" * 50)

    print(f"[INFO] 抓取来源: {args.source}")
    print(f"[INFO] 输出路径: {args.output}")
    print(f"[INFO] 请求延迟: {args.delay}s")
    print()

    # 调用 scraper 模块执行数据抓取
    games = scrape_and_save(args.source, args.output, args.delay)

    # 统计信息
    sources = {}
    for g in games:
        src = g.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1

    print("\n" + "=" * 50)
    print("抓取完成!")
    print(f"  总游戏数: {len(games)}")
    print(f"  数据源: {sources}")
    with_date = sum(1 for g in games if g.get("date"))
    print(f"  有日期: {with_date}, 无日期: {len(games) - with_date}")
    print("=" * 50)


if __name__ == "__main__":
    main()
