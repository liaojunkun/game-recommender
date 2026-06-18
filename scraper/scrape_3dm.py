#!/usr/bin/env python3
"""
3DM 新游中心数据抓取模块

抓取 3DM 网站新游中心页面结构，提取游戏信息并保存为 JSON 文件。

主要数据源:
- 首页"近期新作"板块: https://www.3dmgame.com/
- 首页"近期新作"MORE 链接: https://www.3dmgame.com/games/zq/

注意: new.3dmgame.com DNS 无法解析，改用 www.3dmgame.com

输出: data/3dm_games.json
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
BASE_URL = config.THREEDM_CONFIG["base_url"]
HEADERS = config.THREEDM_CONFIG["headers"]
REQUEST_DELAY = config.REQUEST_DELAY
MAX_RETRIES = config.MAX_RETRIES
OUTPUT_DIR = config.DATA_DIR
OUTPUT_FILE = config.THREEDM_CONFIG["output_file"]


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
            # 3DM 使用 GBK 编码
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.exceptions.RequestException as e:
            print(f"[WARN] 请求失败 (尝试 {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(REQUEST_DELAY * attempt)
            else:
                print(f"[ERROR] 请求 {url} 最终失败")
                return None


def parse_recent_new_games(soup: BeautifulSoup) -> list[dict]:
    """
    从首页解析"近期新作"板块的游戏信息。

    页面结构:
    div.labbox2 (近期新作板块)
      > div.title_
        > div.bt "近期新作"
        > a.more "MORE"
      > ul
        > li.on / li
          > div.box-b
            > a.img (封面图)
            > div.infor
              > a.name (游戏名 + 链接)
              > div.p (日期)
              > div.p (发行信息)
              > div.lab_ (标签)

    Returns:
        游戏字典列表
    """
    games = []

    section = soup.find("div", class_="labbox2")
    if not section:
        print("[WARN] 未找到近期新作板块 (div.labbox2)")
        return games

    items = section.find_all("li")
    if not items:
        print("[WARN] 近期新作板块下没有 li 元素")
        return games

    print(f"[INFO] 近期新作板块找到 {len(items)} 个游戏项")

    for idx, li in enumerate(items, 1):
        box_b = li.find("div", class_="box-b")
        if not box_b:
            print(f"[WARN] 第 {idx} 个游戏项没有找到 box-b div，跳过")
            continue

        game = _extract_game_from_box_b(box_b, source="近期新作")
        if game:
            games.append(game)

    return games


def _extract_game_from_box_b(box_b: BeautifulSoup, source: str = "3DM") -> dict | None:
    """
    从单个游戏卡片中提取数据。

    Args:
        box_b: 游戏卡片的 box-b div
        source: 数据来源标识

    Returns:
        游戏字典 或 None
    """
    # 游戏标题和链接
    title_link = box_b.find("a", class_="name")
    if not title_link:
        return None

    title = title_link.get_text(strip=True)
    url = title_link.get("href", "")
    if url and not url.startswith("http"):
        url = urljoin(BASE_URL, url)

    # 封面图
    img = box_b.find("img")
    image = ""
    if img:
        image = img.get("data-original", "") or img.get("src", "")
        if image and not image.startswith("http"):
            image = urljoin(BASE_URL, image)

    # 发布日期和描述
    p_elements = box_b.find_all("div", class_="p")
    date = ""
    desc = ""

    for p in p_elements:
        text = p.get_text(strip=True)
        if "年" in text or "月" in text:
            date = text
        elif "发行" in text:
            desc = text
        else:
            desc = text

    # 提取纯发布日期 (去掉类型信息)
    date_clean = re.sub(r"\s*\(.*?\)\s*$", "", date).strip() if date else ""

    # 标签 (类型)
    tags_section = box_b.find("div", class_="lab_")
    tags = []
    if tags_section:
        for span in tags_section.find_all("span"):
            t = span.get_text(strip=True)
            if t:
                tags.append(t)

    if not title:
        return None

    return {
        "title": title,
        "url": url,
        "image": image,
        "description": desc,
        "date": date_clean,
        "tags": tags,
        "source": source,
    }


def parse_game_ranking(soup: BeautifulSoup) -> list[dict]:
    """
    从首页解析"游戏排行榜"板块的游戏信息。

    页面结构:
    div.Indexbox9 > ul.list > li.on/li > div.box-b
      > a.img (封面图)
      > div.text
        > a.name_a > div.num (排名)
        > div.name (游戏名)
        > div.lis > p (类型/制作/平台/发行/发售/语言)

    Returns:
        游戏字典列表
    """
    games = []

    rank_section = soup.find("div", class_="Indexbox9")
    if not rank_section:
        print("[WARN] 未找到游戏排行榜板块")
        return games

    items = rank_section.find_all("li")
    if not items:
        return games

    print(f"[INFO] 游戏排行榜板块找到 {len(items)} 个游戏项")

    for idx, li in enumerate(items, 1):
        box_b = li.find("div", class_="box-b")
        if not box_b:
            continue

        # 游戏名在 a.name_a > div.name
        name_a = box_b.find("a", class_="name_a")
        if not name_a:
            continue
        name_div = name_a.find("div", class_="name")
        title = name_div.get_text(strip=True) if name_div else ""

        url = name_a.get("href", "")
        if url and not url.startswith("http"):
            url = urljoin(BASE_URL, url)

        # 封面图在 a.img > img
        img_link = box_b.find("a", class_="img")
        img = img_link.find("img") if img_link else None
        image = ""
        if img:
            image = (img.get("data-original", "") or img.get("src", "")).strip()
            if image and not image.startswith("http"):
                image = urljoin(BASE_URL, image)

        # 从 lis 中提取详细信息
        lis = box_b.find("div", class_="lis")
        desc_parts = []
        date = ""
        if lis:
            for p in lis.find_all("p"):
                p_text = p.get_text(strip=True)
                if "发售" in p_text:
                    date = p_text.replace("发售：", "").strip()
                elif p_text:
                    desc_parts.append(p_text)

        desc = " | ".join(desc_parts[:4]) if desc_parts else ""

        if not title:
            continue

        game = {
            "title": title,
            "url": url,
            "image": image,
            "description": desc,
            "date": date,
            "tags": [],
            "source": "3DM-排行榜",
        }
        games.append(game)

    return games


def parse_lunbo_section(soup: BeautifulSoup) -> list[dict]:
    """
    从首页解析"单机游戏专题推荐"板块的游戏信息。

    页面结构:
    div.Indexbox6-1 (单机游戏专题)
      > div.bjimg (轮播图，可能包含 img)
      > ul/li 或 div.box_
        > h1 (游戏标题)
        > a (第一个链接: "进入专题 >", 第二个链接: 游戏名)
        > p.text_tishi (简介)
        > div.pf (评分)
        > div.bq (标签)

    Returns:
        游戏字典列表
    """
    games = []

    lunbox = soup.find("div", class_="Indexbox6-1")
    if not lunbox:
        print("[WARN] 未找到单机游戏专题板块 (div.Indexbox6-1)")
        return games

    # 遍历所有 a 标签，找到游戏专题链接（跳过"进入专题"导航链接）
    all_links = lunbox.find_all("a", href=True)
    
    # 收集所有专题页面 URL 对应的游戏
    seen_urls = set()
    
    for a in all_links:
        href = a.get("href", "").strip()
        text = a.get_text(strip=True)
        
        # 跳过空链接、商城链接、新闻链接、"进入专题"
        if not href or href == "#":
            continue
        if "mall.3dmgame" in href:
            continue
        if "news" in href:
            continue
        if "进入专题" in text:
            continue
        # 跳过纯图片链接
        if not text:
            continue
        # 游戏页面链接包含 /games/
        if "/games/" not in href:
            continue
        
        url = href if href.startswith("http") else urljoin(BASE_URL, href)
        
        # 去重
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        # 提取游戏标题：找文本为游戏名的链接
        # 同一组 a 标签中，找到 href 相同但文本是游戏名的那个
        title = text
        
        # 过滤无效标题：太短、纯英文大写、导航词
        if len(title) < 2:
            continue
        if title in ("MORE", "更多", "进入专题 >", "进入专题"):
            continue
        
        # 从同组中找游戏图片（通常是第一个或包含 img 的链接）
        # 查找该游戏对应的 img
        image = ""
        # 找图片：在 lunbox 中通过 href 匹配
        for a2 in lunbox.find_all("a", href=lambda x: x and x in href):
            img = a2.find("img")
            if img:
                image = (img.get("data-original", "") or img.get("src", "")).strip()
                if image:
                    break
        
        # 找评分
        rating = ""
        # 找标签
        tags_text = ""
        tags = []
        
        game = {
            "title": title,
            "url": url,
            "image": image,
            "description": "",
            "date": "",
            "tags": tags,
            "source": "3DM-专题",
        }
        if rating:
            game["description"] += f" | 评分: {rating}"
        
        games.append(game)

    if not games:
        print("[WARN] 未从专题板块提取到游戏数据")
        return games

    print(f"[INFO] 专题板块提取 {len(games)} 个游戏")
    return games


def deduplicate(games: list[dict]) -> list[dict]:
    """
    基于 URL 去重，保留第一条。

    Args:
        games: 游戏字典列表

    Returns:
        去重后的游戏字典列表
    """
    seen_urls = set()
    unique = []

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


def scrape_3dm(output_file: str = None, delay: float = REQUEST_DELAY) -> list[dict]:
    """
    抓取 3DM 网站游戏数据。

    数据源优先级:
    1. 首页"近期新作"板块
    2. 首页"游戏排行榜"板块
    3. 首页"专题推荐"板块

    Args:
        output_file: 输出文件路径
        delay: 请求间隔秒数

    Returns:
        游戏字典列表
    """
    all_games = []

    print("=" * 50)
    print("3DM 数据抓取模块启动")
    print(f"目标站点: {BASE_URL}")
    print(f"请求延迟: {delay}s")
    print("=" * 50)

    # 1. 获取首页
    print("\n[STEP 1] 抓取 3DM 首页...")
    html = fetch_page(BASE_URL)
    if not html:
        print("[ERROR] 无法获取 3DM 首页，退出抓取")
        return []

    soup = BeautifulSoup(html, "html.parser")

    # 2. 解析"近期新作"板块
    print("\n[STEP 2] 解析'近期新作'板块...")
    recent_games = parse_recent_new_games(soup)
    all_games.extend(recent_games)
    print(f"  -> 提取 {len(recent_games)} 个游戏")

    # 3. 解析"游戏排行榜"板块
    print("\n[STEP 3] 解析'游戏排行榜'板块...")
    time.sleep(delay)  # 遵守 robots.txt 友好原则
    rank_games = parse_game_ranking(soup)
    all_games.extend(rank_games)
    print(f"  -> 提取 {len(rank_games)} 个游戏")

    # 4. 解析专题推荐板块
    print("\n[STEP 4] 解析专题推荐板块...")
    time.sleep(delay)
    lunbo_games = parse_lunbo_section(soup)
    all_games.extend(lunbo_games)
    print(f"  -> 提取 {len(lunbo_games)} 个游戏")

    # 5. 去重
    print("\n[STEP 5] 去重...")
    all_games = deduplicate(all_games)
    print(f"  -> 去重后剩余 {len(all_games)} 个游戏")

    # 6. 保存
    print("\n[STEP 6] 保存数据...")
    save_games(all_games, output_file)

    # 7. 输出摘要
    print("\n" + "=" * 50)
    print(f"抓取完成! 共提取 {len(all_games)} 个游戏")
    for g in all_games:
        print(f"  - {g['title']} | {g['date']} | {g['tags']}")
    print("=" * 50)

    return all_games


if __name__ == "__main__":
    scrape_3dm()
