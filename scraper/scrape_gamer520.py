#!/usr/bin/env python3
"""
Gamer520 PC游戏数据抓取模块

抓取 Gamer520 网站的 PC 游戏列表页面，提取游戏信息并保存为 JSON 文件。

主要数据源:
- PC游戏列表页: https://www.gamer520.com/pcplay

输出: data/gamer520_games.json
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
BASE_URL = config.GAMER520_CONFIG["base_url"]
LIST_URL = config.GAMER520_CONFIG["list_url"]
HEADERS = config.GAMER520_CONFIG["headers"]
REQUEST_DELAY = config.REQUEST_DELAY
MAX_RETRIES = config.MAX_RETRIES
MAX_PAGES_DATE = config.GAMER520_CONFIG["max_pages_date"]
MAX_PAGES_HOT = config.GAMER520_CONFIG["max_pages_hot"]
MAX_PAGES_COMMENT = config.GAMER520_CONFIG["max_pages_comment"]
OUTPUT_FILE = config.GAMER520_CONFIG["output_file"]


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
        except requests.exceptions.HTTPError as e:
            print(f"[WARN] HTTP错误 (尝试 {attempt}/{retries}): {e}")
            print(f"  状态码: {e.response.status_code}")
            # 只打印关键响应头，避免过长
            important_headers = {k: v for k, v in e.response.headers.items() 
                                if k.lower() in ('server', 'cf-ray', 'cf-mitigated', 'content-type', 'set-cookie')}
            print(f"  关键响应头: {important_headers}")
            # 尝试解码响应体，失败则跳过
            try:
                body_text = e.response.text[:300]
                if body_text.isprintable() or len(body_text.encode('utf-8', errors='ignore')) > 100:
                    print(f"  响应体(前300字符): {body_text}")
                else:
                    print(f"  响应体: [非文本内容，长度 {len(e.response.content)} 字节]")
            except Exception:
                print(f"  响应体: [无法解码，长度 {len(e.response.content)} 字节]")
            if attempt < retries:
                time.sleep(REQUEST_DELAY * attempt)
            else:
                print(f"[ERROR] 请求 {url} 最终失败")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[WARN] 请求失败 (尝试 {attempt}/{retries}): {type(e).__name__}: {e}")
            if attempt < retries:
                time.sleep(REQUEST_DELAY * attempt)
            else:
                print(f"[ERROR] 请求 {url} 最终失败")
                return None


def parse_game_list_page(soup: BeautifulSoup, order_type: str = "date", rank_offset: int = 0) -> list[dict]:
    """
    从 PC 游戏列表页解析游戏信息。

    页面结构:
    每个游戏在 <article> 元素中，包含:
      - <div class="entry-media"> 中的图片
      - <div class="entry-footer"> 中的时间信息（<time> 标签的 datetime 属性）

    Args:
        soup: BeautifulSoup 对象
        order_type: 排序类型 (date/hot/comment_count)
        rank_offset: 排名偏移量（之前页面累计的游戏数量）

    Returns:
        游戏字典列表
    """
    games = []

    # 查找所有游戏 article 元素
    articles = soup.find_all("article", class_="post")

    seen_urls = set()
    rank = rank_offset  # 使用传入的偏移量作为起始排名

    for article in articles:
        # 提取详情页链接
        link = article.find("a", href=re.compile(r"/\d+\.html$"))
        if not link:
            continue
        
        detail_url = link.get("href", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = urljoin(BASE_URL, detail_url)

        # 提取图片信息
        img = article.find("img")
        if not img:
            continue

        # 提取标题（优先从 alt 属性，其次从 title 属性，最后从 h2.entry-title）
        title = img.get("alt", "").strip() or img.get("title", "").strip()
        if not title:
            # 尝试从 h2.entry-title 获取标题
            title_elem = article.find("h2", class_="entry-title")
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        if not title:
            continue

        # 提取图片 URL（优先从懒加载属性获取）
        image = (
            img.get("data-src", "")
            or img.get("data-original", "")
            or img.get("data-lazy-src", "")
            or img.get("data-lazy", "")
            or img.get("src", "")
        )
        # 过滤掉 base64 占位图
        if image and image.startswith("data:"):
            image = ""
        if image and not image.startswith("http"):
            image = urljoin(BASE_URL, image)

        # 提取时间信息（从 time 元素的 datetime 属性）
        date = ""
        time_elem = article.find("time")
        if time_elem:
            # 优先使用 datetime 属性（ISO 格式）
            iso_date = time_elem.get("datetime", "")
            if iso_date:
                # 将 ISO 格式转换为 "YYYY-MM-DD HH:MM"
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
                    date = dt.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError):
                    date = iso_date
            # 如果没有 datetime 属性，使用文本内容
            if not date:
                date = time_elem.get_text(strip=True)

        # 去重
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)

        rank += 1
        game = {
            "title": title,
            "url": detail_url,
            "image": image,
            "description": "",
            "date": date,
            "tags": [],
            "source": "GAMER520",
        }
        # 只记录热度和评论数量的排名，日期排序前端直接用 date 字段
        if order_type != "date":
            game[f"rank_{order_type}"] = rank
        games.append(game)

    return games


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


def scrape_gamer520(output_file: str = None, delay: float = REQUEST_DELAY) -> list[dict]:
    """
    抓取 Gamer520 网站游戏数据。

    分别抓取三种排序的数据：
    - 默认（按日期）
    - 热度（hot）
    - 评论数量（comment_count）

    智能去重：如果游戏已在之前的排序中抓取过，后续排序只记录排名。

    Args:
        output_file: 输出文件路径
        delay: 请求间隔秒数

    Returns:
        游戏字典列表
    """
    # 已知游戏字典：url -> game dict，在抓取过程中实时更新
    known_games = {}
    # 每页固定显示的游戏数量（用于计算排名偏移）
    PAGE_SIZE = 20

    # 定义要抓取的排序类型及对应URL和最大页数
    order_configs = [
        {"order": "date", "base_path": LIST_URL, "query": "", "label": "默认（日期）", "max_pages": MAX_PAGES_DATE},
        {"order": "hot", "base_path": LIST_URL, "query": "order=hot", "label": "热度", "max_pages": MAX_PAGES_HOT},
        {"order": "comment_count", "base_path": LIST_URL, "query": "order=comment_count", "label": "评论数量", "max_pages": MAX_PAGES_COMMENT},
    ]

    print("=" * 50)
    print("Gamer520 数据抓取模块启动")
    print(f"目标站点: {LIST_URL}")
    print(f"排序类型: 日期({MAX_PAGES_DATE}页)、热度({MAX_PAGES_HOT}页)、评论数量({MAX_PAGES_COMMENT}页)")
    print(f"请求延迟: {delay}s")
    print("=" * 50)

    for order_cfg in order_configs:
        order_type = order_cfg["order"]
        base_path = order_cfg["base_path"]
        query = order_cfg["query"]
        label = order_cfg["label"]
        max_pages = order_cfg["max_pages"]

        print(f"\n--- 抓取排序: {label} (最大{max_pages}页) ---")

        for page in range(1, max_pages + 1):
            # 构建URL：第1页用基础路径，后续页用 /page/N 格式
            if page == 1:
                page_url = base_path
            else:
                page_url = f"{base_path}/page/{page}"

            # 添加查询参数
            if query:
                page_url = f"{page_url}?{query}"

            print(f"  [页 {page}] {page_url}")

            html = fetch_page(page_url)
            if not html:
                print(f"  [WARN] 第 {page} 页获取失败，停止该排序的抓取")
                break

            soup = BeautifulSoup(html, "html.parser")
            rank_offset = (page - 1) * PAGE_SIZE
            page_games = parse_game_list_page(soup, order_type, rank_offset=rank_offset)

            if not page_games:
                print(f"  [WARN] 第 {page} 页未找到游戏，停止该排序的抓取")
                break

            # 智能去重：新游戏完整记录，已知游戏只更新排名
            new_count = 0
            rank_key = f"rank_{order_type}"
            for game in page_games:
                url = game.get("url", "")
                if url in known_games:
                    # 已知游戏：只更新当前排序的排名
                    if rank_key in game:
                        known_games[url][rank_key] = game[rank_key]
                else:
                    known_games[url] = game
                    new_count += 1

            print(f"    -> 本页 {len(page_games)} 个，新增 {new_count} 个，已知 {len(page_games) - new_count} 个，累计 {len(known_games)} 个")

            # 请求间隔
            if page < max_pages:
                time.sleep(delay)

    all_games = list(known_games.values())

    # 保存
    print("\n[STEP] 保存数据...")
    save_games(all_games, output_file)

    # 输出摘要
    print("\n" + "=" * 50)
    print(f"抓取完成! 共 {len(all_games)} 个游戏")
    for g in all_games[:10]:
        print(f"  - {g['title']}")
    if len(all_games) > 10:
        print(f"  ... 还有 {len(all_games) - 10} 个游戏")
    print("=" * 50)

    return all_games


if __name__ == "__main__":
    scrape_gamer520()
