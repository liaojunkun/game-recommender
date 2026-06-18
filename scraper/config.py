#!/usr/bin/env python3
"""
配置文件：集中管理爬虫模块的配置参数。
"""

import os
from pathlib import Path

# 项目根目录（scraper 的父目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# 通用请求头
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# 通用配置
REQUEST_DELAY = 1.0  # 请求间隔秒数（优化：从2秒减到1秒）
MAX_RETRIES = 3  # 最大重试次数
REQUEST_TIMEOUT = 20  # 请求超时秒数

# 3DM 配置
THREEDM_CONFIG = {
    "base_url": "https://www.3dmgame.com/",
    "headers": DEFAULT_HEADERS,
    "output_file": DATA_DIR / "3dm_games.json",
}

# 游侠网配置
ALI213_CONFIG = {
    "base_url": "https://www.ali213.net/",
    "rank_url": "https://www.ali213.net/paihb.html",
    "headers": DEFAULT_HEADERS,
    "output_file": DATA_DIR / "ali213_games.json",
}

# Gamer520 配置
GAMER520_CONFIG = {
    "base_url": "https://www.gamer520.com",
    "list_url": "https://www.gamer520.com/pcplay",
    "headers": DEFAULT_HEADERS,
    "max_pages_date": 10,        # 默认（发布日期）最大抓取页数
    "max_pages_hot": 5,         # 热度最大抓取页数
    "max_pages_comment": 5,     # 评论数量最大抓取页数
    "output_file": DATA_DIR / "gamer520_games.json",
}

# 聚合配置
AGGREGATE_CONFIG = {
    "output_file": DATA_DIR / "games.json",
}
