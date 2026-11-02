#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1A2X 社区 (https://1a2x.com) 每日自动签到
机制（实测于站点登录态）：
  1) GET  /growth         -> 页面内含 <form class="daily-checkin" action="/growth/checkin">
                             以及 <input type="hidden" name="_csrf" value="...">
  2) POST /growth/checkin -> _csrf=<token>&return_to=/growth
  3) 已签到特征：按钮 disabled 且文案「今日已签到 +5」
只依赖 Python 标准库。
"""
import os
import re
import sys
import time
import random
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar

BASE = "https://1a2x.com"
CHECKIN_PATH = "/growth/checkin"
GROWTH_PATH = "/growth"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

COOKIE_ENV = "A2X_COOKIE"
MAX_ATTEMPTS = 5
RETRY_SLEEP = 4


try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    print("[1a2x] " + str(msg), flush=True)


def build_opener(cookie_str):
    jar = http.cookiejar.CookieJar()
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        name, value = name.strip(), value.strip()
        jar.set_cookie(http.cookiejar.Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain="1a2x.com", domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=name.startswith("__Host-"),
            expires=None, discard=False, comment=None, comment_url=None,
            rest={"HttpOnly": None}, rfc2109=False,
        ))
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
        ("Accept-Encoding", "identity"),
        ("Referer", BASE + GROWTH_PATH),
        ("Origin", BASE),
        ("Cache-Control", "no-cache"),
    ]
    return opener


def fetch(opener, path, data=None):
    url = BASE + path
    body = urllib.parse.urlencode(data).encode() if data else None
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, data=body)
            if body:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with opener.open(req, timeout=45) as r:
                return r.status, r.read().decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace") if e.fp else ""
            if e.code in (403, 429, 502, 503, 520, 521, 522, 524) and attempt < MAX_ATTEMPTS:
                last = "HTTP %s" % e.code
            else:
                return e.code, txt, url
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        wait = RETRY_SLEEP + random.uniform(0, 2) * attempt
        log("第 %d 次请求失败（%s），%.1fs 后重试" % (attempt, last, wait))
        time.sleep(wait)
    return 0, "", url


def extract_csrf(html):
    for pat in (r'name="_csrf"\s+value="([^"]+)"',
                r'name="csrf-token"\s+content="([^"]+)"',
                r'"csrfToken"\s*:\s*"([^"]+)"'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def is_logged_in(html):
    return ("/logout" in html) or ("header-user" in html)


def already_done(html):
    """双判据：文案命中，或签到按钮带 disabled（文案改版时仍能判定）。"""
    if "今日已签到" in html or "已签到" in html:
        return True
    m = re.search(r'<form[^>]*class="[^"]*daily-checkin[^"]*".*?</form>', html, re.S)
    if m:
        form = m.group(0)
        btn = re.search(r"<button[^>]*>", form)
        if btn and "disabled" in btn.group(0):
            return True
    return False


def bananas(html):
    m = re.search(r'data-member-metric="bananas"[^>]*>[^<]*(?:<(?!/?dl)[^>]*>[^<]*)*?<dd>(\d+)</dd>', html, re.S)
    return int(m.group(1)) if m else None


def main():
    cookie = os.environ.get(COOKIE_ENV, "").strip()
    if not cookie:
        log("缺少环境变量 " + COOKIE_ENV + "，请在仓库 Secrets 中配置登录后的完整 Cookie")
        return 2
    if "__Host-nc.sid" not in cookie:
        log("警告：Cookie 中未发现 __Host-nc.sid，登录态很可能无效")

    opener = build_opener(cookie)
    status, home, _ = fetch(opener, GROWTH_PATH)
    if status != 200 or len(home) < 1000:
        log("打开 %s 失败（status=%s, len=%s）" % (GROWTH_PATH, status, len(home)))
        return 3

    if not is_logged_in(home):
        log("Cookie 已失效：页面显示未登录，请重新抓取 Cookie 并更新 Secret")
        return 4

    if already_done(home):
        log("今日已签到，无需重复操作（当前香蕉：%s）" % bananas(home))
        return 0

    csrf = extract_csrf(home)
    if not csrf:
        log("未能从页面提取 _csrf token，站点结构可能已变更")
        return 5

    log("检测到未签到，正在提交签到请求…")
    status, body, _ = fetch(opener, CHECKIN_PATH, {"_csrf": csrf, "return_to": GROWTH_PATH})

    if status in (200, 301, 302, 303):
        if "Invalid form token" in body or "表单已过期" in body:
            log("CSRF token 校验失败，请检查 Cookie 是否为最新")
            return 6
        _, after, _ = fetch(opener, GROWTH_PATH)
        if already_done(after):
            log("✅ 签到成功（当前香蕉：%s）" % bananas(after))
            return 0
        log("请求已发出，但页面未显示签到成功，可能已被签到或触发风控")
        log("响应片段：" + re.sub(r"\s+", " ", body[:300]))
        return 7

    log("签到请求异常：HTTP %s" % status)
    return 8


if __name__ == "__main__":
    sys.exit(main())
