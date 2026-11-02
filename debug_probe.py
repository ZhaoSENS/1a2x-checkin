# -*- coding: utf-8 -*-
"""排障用：打印签到流程每一步的原始状态，不修改任何东西。
用法：设置环境变量 A2X_COOKIE 后运行 python debug_probe.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkin as C

cookie = os.environ.get(C.COOKIE_ENV, "").strip()
if not cookie:
    print("请先设置环境变量 " + C.COOKIE_ENV)
    sys.exit(2)

op = C.build_opener(cookie)
st, home, _ = C.fetch(op, C.GROWTH_PATH)
print("GET %s -> %s len=%s logged_in=%s done=%s" % (C.GROWTH_PATH, st, len(home), C.is_logged_in(home), C.already_done(home)))
tok = C.extract_csrf(home)
print("csrf_len=%s" % len(tok or ""))
st2, body, url2 = C.fetch(op, C.CHECKIN_PATH, {"_csrf": tok, "return_to": C.GROWTH_PATH})
print("POST %s -> %s final=%s len=%s invalid_token=%s" % (C.CHECKIN_PATH, st2, url2, len(body), "Invalid form token" in body))
st3, after, _ = C.fetch(op, C.GROWTH_PATH)
print("GET after -> %s done=%s bananas=%s" % (st3, C.already_done(after), C.bananas(after)))
