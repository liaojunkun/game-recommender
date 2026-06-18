#!/usr/bin/env python3
"""
游侠网 (ali213.net) 单机游戏排行榜数据抓取模块

抓取游侠网排行榜页面结构，提取游戏信息并保存为 JSON 文件。

主要数据源:
- 游侠网单机游戏排行榜: https://www.ali213.net/paihb.html

排行榜分类:
1. 新游戏期待榜 (热门榜) - 20 个游戏
2. 新游戏排行榜 (好评榜) - 20 个游戏
3. 年度上市单机游戏排行榜 - 19 个游戏

输出: data/ali213_games.json
"""

import json
import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from . import config

# ---- 配置 ----
BASE_URL = config.ALI213_CONFIG["base_url"]
RANK_URL = config.ALI213_CONFIG["rank_url"]
HEADERS = config.ALI213_CONFIG["headers"]
REQUEST_DELAY = config.REQUEST_DELAY
MAX_RETRIES = config.MAX_RETRIES
OUTPUT_DIR = config.DATA_DIR
OUTPUT_FILE = config.ALI213_CONFIG["output_file"]


def fetch_page(url: str, headers: dict = None, retries: int = MAX_RETRIES) -> str | None:
    """
    获取页面 HTML 内容，带重试和错误处理。

    Args:
        url: 目标 URL
        headers: 请求头
        retries: 重试次数

    Returns:
        HTML 字符串，失败返回 None
    """
    if headers is None:
        headers = HEADERS

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.exceptions.RequestException as e:
            print(f"[WARN] 请求失败 (尝试 {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(REQUEST_DELAY * attempt)
            else:
                print(f"[ERROR] 请求 {url} 最终失败")
                return None


def extract_game_info(item: BeautifulSoup, rank: int = 0, source: str = "") -> dict | None:
    """
    从单个游戏排名卡片中提取数据。

    页面结构 (for_num / for_num1 / for_num2 / for_num3):
    div.for_num
      > div.part1
        > div.num(1/2/3) - 排名
        > div.pho > a > img - 封面图
        > div.infos
          > div.titdata > a > div - 游戏标题
          > div.contdata
            > div.type - 游戏类型
            > div.times - 发布日期
            > div.region - 链接区域

    Args:
        item: 游戏卡片 div
        rank: 排名序号
        source: 榜单来源

    Returns:
        游戏字典 或 None
    """
    # 排名
    num_el = item.find(["div.num1", "div.num2", "div.num3", "div.num", "div.nums"])
    rank_el = item.find(["div.num1", "div.num2", "div.num3", "div.num", "div.nums"])
    rank_text = rank_el.get_text(strip=True) if rank_el else str(rank)

    # 标题和链接 (通过 title 属性获取)
    title_a = item.find("a", title=True)
    if not title_a:
        return None

    title = title_a.get("title", "").strip()
    url = title_a.get("href", "").strip()

    if not title:
        return None

    if url and not url.startswith("http"):
        url = urljoin(BASE_URL, url)

    # 封面图
    img = item.find("img")
    image = ""
    if img:
        image = img.get("src", "").strip()
        if image and not image.startswith("http"):
            image = urljoin(BASE_URL, image)

    # 游戏类型
    type_el = item.find("div", class_="type")
    game_type = type_el.get_text(strip=True) if type_el else ""

    # 发布日期
    time_el = item.find("div", class_="times")
    pub_date = time_el.get_text(strip=True) if time_el else ""

    # 简介: 从 title 属性中提取英文名
    desc = ""
    if title_a.get("title"):
        # 尝试提取英文名 (在第一个中文标点后)
        match = re.match(r"([\u4e00-\u9fff]+[:：\s]*)(.+)", title_a.get("title"))
        if match:
            desc = title_a.get("title").strip()

    return {
        "title": title,
        "url": url,
        "image": image,
        "description": desc,
        "date": pub_date,
        "type": game_type,
        "rank": int(rank_text) if rank_text.isdigit() else rank,
        "source": source,
    }


def parse_hot_ranking(soup: BeautifulSoup) -> list[dict]:
    """
    解析"新游戏期待榜" (热门榜)。

    页面结构:
    div.forGs > div.for_num1/2/3/for_num (共20个)

    Returns:
        游戏字典列表
    """
    games = []
    section = soup.find("div", class_="forGs")
    if not section:
        print("[WARN] 未找到新游戏期待榜板块 (div.forGs)")
        return games

    print("[INFO] 解析新游戏期待榜...")

    # Top 3 有单独 class，其余是 for_num
    top_classes = ["for_num1", "for_num2", "for_num3"]
    for cls in top_classes:
        item = section.find("div", class_=cls)
        if item:
            rank = int(cls.replace("for_num", ""))
            game = extract_game_info(item, rank=rank, source="ali213-期待榜")
            if game:
                games.append(game)

    # 其余游戏 (for_num, 可能有 after10 后缀)
    rest_items = section.find_all("div", class_=["for_num", re.compile(r"for_num$")])
    for idx, item in enumerate(rest_items, 4):
        game = extract_game_info(item, rank=idx, source="ali213-期待榜")
        if game:
            games.append(game)

    print(f"  -> 提取 {len(games)} 个期待榜游戏")
    return games


def parse_good_ranking(soup: BeautifulSoup) -> list[dict]:
    """
    解析"新游戏排行榜" (好评榜)。

    页面结构:
    div.newGs > div.for_num1/2/3/for_num (共20个)

    Returns:
        游戏字典列表
    """
    games = []
    section = soup.find("div", class_="newGs")
    if not section:
        print("[WARN] 未找到新游戏排行榜板块 (div.newGs)")
        return games

    print("[INFO] 解析新游戏排行榜...")

    top_classes = ["for_num1", "for_num2", "for_num3"]
    for cls in top_classes:
        item = section.find("div", class_=cls)
        if item:
            rank = int(cls.replace("for_num", ""))
            game = extract_game_info(item, rank=rank, source="ali213-好评榜")
            if game:
                games.append(game)

    rest_items = section.find_all("div", class_=["for_num", re.compile(r"for_num$")])
    for idx, item in enumerate(rest_items, 4):
        game = extract_game_info(item, rank=idx, source="ali213-好评榜")
        if game:
            games.append(game)

    print(f"  -> 提取 {len(games)} 个好评榜游戏")
    return games


def parse_year_ranking(soup: BeautifulSoup) -> list[dict]:
    """
    解析"年度上市单机游戏排行榜"。

    页面结构:
    div.yearGs_cont > div.yycont_lst > div.gsPlay_cont (共19个)

    每个游戏项结构:
    div.gsPlay_cont
      > div.lst_cont > div.num_gs - 排名
      > div.lst_cont > div.detail_cont > a > img + span - 游戏信息

    Returns:
        游戏字典列表
    """
    games = []
    section = soup.find("div", class_="yycont_lst")
    if not section:
        print("[WARN] 未找到年度排行榜游戏列表 (div.yycont_lst)")
        return games

    print("[INFO] 解析年度上市单机游戏排行榜...")

    items = section.find_all("div", class_="gsPlay_cont")
    if not items:
        print("[WARN] 年度排行榜下没有游戏项")
        return games

    for idx, item in enumerate(items, 1):
        # 排名
        num_gs = item.find("div", class_="num_gs")
        rank_text = num_gs.get_text(strip=True) if num_gs else str(idx)

        # 标题和链接
        detail = item.find("div", class_="detail_cont")
        if not detail:
            continue

        title_a = detail.find("a", title=True)
        if not title_a:
            continue

        title = title_a.get("title", "").strip()
        url = title_a.get("href", "").strip()

        if not title:
            continue

        if url and not url.startswith("http"):
            url = urljoin(BASE_URL, url)

        # 封面图
        img = detail.find("img")
        image = ""
        if img:
            image = img.get("src", "").strip()
            if image and not image.startswith("http"):
                image = urljoin(BASE_URL, image)

        # 年度榜单没有类型和日期信息
        game = {
            "title": title,
            "url": url,
            "image": image,
            "description": "",
            "date": "",
            "type": "",
            "rank": int(rank_text) if rank_text.isdigit() else idx,
            "source": "ali213-年度榜",
        }
        games.append(game)

    print(f"  -> 提取 {len(games)} 个年度榜游戏")
    return games


def parse_shortcuts(soup: BeautifulSoup) -> list[dict]:
    """
    解析页面顶部的快捷推荐游戏 (近期新作、即将上市)。

    页面结构:
    div.tj-game > div.rmzt (近期新作) / div.jqxz (即将上市) > div.tj-li > a

    Returns:
        游戏字典列表
    """
    games = []
    tj_game = soup.find("div", class_="tj-game")
    if not tj_game:
        return games

    print("[INFO] 解析快捷推荐游戏...")

    for section_class in ["rmzt", "jqxz"]:
        section = tj_game.find("div", class_=section_class)
        if not section:
            continue

        source = "ali213-近期新作" if section_class == "rmzt" else "ali213-即将上市"
        items = section.find_all("div", class_="tj-li")
        if not items:
            continue

        for idx, item in enumerate(items, 1):
            a = item.find("a", title=True)
            if not a:
                continue

            title = a.get("title", "").strip()
            url = a.get("href", "").strip()

            if not title or len(title) < 2:
                continue

            # 跳过广告/推广链接
            if any(kw in url for kw in ["g.ieeod0.com", "tp.9377s.com"]):
                continue

            if url and not url.startswith("http"):
                url = urljoin(BASE_URL, url)

            games.append({
                "title": title,
                "url": url,
                "image": "",
                "description": "",
                "date": "",
                "type": "",
                "rank": idx,
                "source": source,
            })

    if games:
        print(f"  -> 提取 {len(games)} 个快捷推荐游戏")
    return games


def deduplicate(games: list[dict]) -> list[dict]:
    """
    基于 URL 去重，保留排名最高的条目 (来自主排行榜)。

    Args:
        games: 游戏字典列表

    Returns:
        去重后的游戏字典列表
    """
    seen_urls = set()
    unique = []

    # 优先级: 主排行榜 > 快捷推荐
    # 已按此顺序添加，所以直接去重即可
    for game in games:
        url = game.get("url", "").strip()
        if url and url in seen_urls:
            print(f"[INFO] 去重: 跳过重复游戏 {game['title']} ({url})")
            continue
        if url:
            seen_urls.add(url)
        unique.append(game)

    return unique


def save_games(games: list[dict], output_file: str = None) -> str:
    """
    将游戏数据保存为 JSON 文件。

    Args:
        games: 游戏字典列表
        output_file: 输出文件路径

    Returns:
        输出文件路径
    """
    if output_file is None:
        output_file = OUTPUT_FILE

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 已保存 {len(games)} 条游戏数据到 {output_file}")
    return output_file


def scrape_ali213(output_file: str = None, delay: float = REQUEST_DELAY) -> list[dict]:
    """
    抓取游侠网单机游戏排行榜数据。

    数据源优先级:
    1. 新游戏期待榜 (热门榜) - 20 个游戏
    2. 新游戏排行榜 (好评榜) - 20 个游戏
    3. 年度上市单机游戏排行榜 - 19 个游戏
    4. 快捷推荐 (近期新作/即将上市) - 补充数据

    Args:
        output_file: 输出文件路径
        delay: 请求间隔秒数

    Returns:
        游戏字典列表
    """
    all_games = []

    print("=" * 50)
    print("游侠网数据抓取模块启动")
    print(f"目标站点: {RANK_URL}")
    print(f"请求延迟: {delay}s")
    print("=" * 50)

    # 1. 获取排行榜页面
    print("\n[STEP 1] 抓取游侠网排行榜页面...")
    html = fetch_page(RANK_URL)
    if not html:
        print("[ERROR] 无法获取游侠网排行榜页面，退出抓取")
        return []

    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(strip=True) if soup.title else "未知"
    print(f"  -> 页面标题: {page_title}")

    # 2. 解析新游戏期待榜 (热门榜)
    print("\n[STEP 2] 解析新游戏期待榜...")
    time.sleep(delay)
    hot_games = parse_hot_ranking(soup)
    all_games.extend(hot_games)
    print(f"  -> 提取 {len(hot_games)} 个游戏")

    # 3. 解析新游戏排行榜 (好评榜)
    print("\n[STEP 3] 解析新游戏排行榜...")
    time.sleep(delay)
    good_games = parse_good_ranking(soup)
    all_games.extend(good_games)
    print(f"  -> 提取 {len(good_games)} 个游戏")

    # 4. 解析年度排行榜
    print("\n[STEP 4] 解析年度上市单机游戏排行榜...")
    time.sleep(delay)
    year_games = parse_year_ranking(soup)
    all_games.extend(year_games)
    print(f"  -> 提取 {len(year_games)} 个游戏")

    # 5. 解析快捷推荐
    print("\n[STEP 5] 解析快捷推荐游戏...")
    time.sleep(delay)
    shortcut_games = parse_shortcuts(soup)
    all_games.extend(shortcut_games)
    print(f"  -> 提取 {len(shortcut_games)} 个游戏")

    # 6. 去重
    print("\n[STEP 6] 去重...")
    all_games = deduplicate(all_games)
    print(f"  -> 去重后剩余 {len(all_games)} 个游戏")

    # 7. 保存
    print("\n[STEP 7] 保存数据...")
    save_games(all_games, output_file)

    # 8. 输出摘要
    print("\n" + "=" * 50)
    print(f"抓取完成! 共提取 {len(all_games)} 个游戏")
    source_counts = {}
    for g in all_games:
        src = g.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in source_counts.items():
        print(f"  - {src}: {count}")
    for g in all_games:
        print(f"  #{g.get('rank', '?')} | {g['title']} | {g['date']} | {g.get('type', '')}")
    print("=" * 50)

    return all_games


if __name__ == "__main__":
    scrape_ali213()
