#!/usr/bin/env python3
"""从 zdaye.com 免费代理页抓取代理列表，输出 JSON 格式。

用法:
    python fetch_proxies.py           # 打印 JSON
    python fetch_proxies.py --update  # 更新 config.json 的 proxies 字段
"""

import sys
import json
import os
import re
from urllib.request import urlopen, Request
from urllib.parse import quote

ZDYE_URL = "https://www.zdaye.com/free/?ip_adr=&checktime=&sleep=1&cunhuo=&dengji=&protocol=&yys=&px="
PAGES = 5  # 抓取前 N 页

PROTO_MAP = {
    "HTTP": "http",
    "HTTPS": "https",
    "SOCKS4": "socks4",
    "SOCKS5": "socks5",
}


def fetch_page(url):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    resp = urlopen(req, timeout=15)
    return resp.read().decode("utf-8", errors="ignore")


def parse_proxies(html):
    """从 HTML 中提取 IP:端口 和协议。"""
    proxies = []
    # 匹配表格行: <td>IP</td> ... Port ... 协议
    # 格式: IP数字 Port：数字 协议
    pattern = re.compile(
        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?'
        r'Port[：:]\s*(\d{2,5}).*?'
        r'(HTTP|HTTPS|SOCKS4|SOCKS5)',
        re.DOTALL
    )
    for match in pattern.finditer(html):
        ip = match.group(1)
        port = match.group(2)
        proto = PROTO_MAP.get(match.group(3), "http")
        proxies.append(f"{proto}://{ip}:{port}")
    return proxies


def main():
    all_proxies = []
    for page in range(1, PAGES + 1):
        try:
            url = ZDYE_URL if page == 1 else ZDYE_URL.replace("zdaye.com/free/?", f"zdaye.com/free/{page}?")
            html = fetch_page(url)
            proxies = parse_proxies(html)
            all_proxies.extend(proxies)
            print(f"  第 {page} 页: {len(proxies)} 个", file=sys.stderr)
        except Exception as e:
            print(f"  第 {page} 页失败: {e}", file=sys.stderr)

    # 去重
    seen = set()
    unique = []
    for p in all_proxies:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    print(f"  共 {len(unique)} 个去重代理", file=sys.stderr)

    if "--update" in sys.argv:
        # 更新 config.json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if not os.path.exists(config_path):
            print("config.json 不存在，请先创建。", file=sys.stderr)
            sys.exit(1)
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        config["proxies"] = unique
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"  已更新 config.json (proxies: {len(unique)} 个)", file=sys.stderr)
    else:
        print(json.dumps(unique, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
