# 1A2X 社区每日自动签到（GitHub Actions）

目标站点：https://1a2x.com/

## 一、站点签到机制（已实测）

| 项目 | 值 |
|---|---|
| 签到接口 | `POST https://1a2x.com/growth/checkin` |
| 表单字段 | `_csrf=<token>`、`return_to=/growth` |
| CSRF 来源 | 页面 `<input type="hidden" name="_csrf" value="...">`（等同 `<meta name="csrf-token">`） |
| 入口页面 | `/growth`（侧边栏「社区成长」），首页右侧会员面板也有同一表单 |
| 已签到特征 | 按钮 `disabled`，文案「今日已签到 +5」 |
| 奖励 | 每日 +5 香蕉；累计签到 30 天「活跃成员」、365 天「签到达人」勋章 |
| 必需 Cookie | `__Host-nc.sid`（会话）、`__Host-nc.csrf`、`server_session_43237463` |

站点全站走 Cloudflare，直连常出现连接重置，脚本已内置 5 次重试 + 随机退避。

## 二、目录结构

```
1a2x-checkin/
├─ checkin.py                       # 签到主程序（仅标准库）
├─ .github/workflows/checkin.yml    # 定时任务
└─ README.md
```

## 三、部署步骤

### 1. 抓取登录后的 Cookie

浏览器登录 https://1a2x.com/ ，F12 → Application → Cookies → `https://1a2x.com`，
把这几条拼成一行 `name=value; name=value`（至少包含 `__Host-nc.sid`）：

```
__Host-nc.sid=...; __Host-nc.csrf=...; server_session_43237463=...; nc.bid=...
```

> 更省事：Network 面板任选一个已登录请求，复制请求头整条 `Cookie:` 值。

### 2. 建仓库并上传

```bash
git init 1a2x-checkin && cd 1a2x-checkin
# 放入 checkin.py 与 .github/workflows/checkin.yml
git add . && git commit -m "feat: 1a2x daily check-in"
git branch -M main
git remote add origin https://github.com/<你的用户名>/1a2x-checkin.git
git push -u origin main
```

### 3. 配置 Secret

仓库 → Settings → Secrets and variables → Actions → New repository secret

- Name: `A2X_COOKIE`
- Value: 第 1 步拼好的整条 Cookie

### 4. 手动跑一次验证

Actions → **1A2X Daily Check-in** → Run workflow。

成功：

```
[1a2x] 检测到未签到，正在提交签到请求…
[1a2x] ✅ 签到成功（当前香蕉：21）
```

已签到：

```
[1a2x] 今日已签到，无需重复操作（当前香蕉：16）
```

## 四、时间说明

GitHub Actions 的 cron 是 **UTC**：

| cron | 北京时间 |
|---|---|
| `5 0 * * *` | 08:05 |
| `5 12 * * *` | 20:05 |

脚本幂等，重复执行只提示「今日已签到」；双时段还能兜住 GitHub 调度延迟（高峰期 cron 常延迟 10~60 分钟）。

## 五、退出码对照

| 码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功 / 今日已签到 | 无需操作 |
| 2 | 未配置 `A2X_COOKIE` | 检查 Secret 名称 |
| 3 | 打开 /growth 失败 | Cloudflare 拦截或网络问题，重跑 |
| 4 | Cookie 失效 | 重新抓 Cookie 更新 Secret |
| 5 | 提取不到 `_csrf` | 站点改版，更新正则 |
| 6 | 表单 token 校验失败 | Cookie 过期 |
| 7 | 请求成功但页面无签到标记 | 可能已被签到，人工看一眼 |

## 六、Cookie 失效的常见原因

1. 在浏览器点了「退出登录」——立刻使该 session 失效
2. 站点清理会话（约 30 天）
3. 修改密码 / 开关两步验证
4. 站点改版导致 session 表重建

建议每周瞄一眼 Actions 运行记录。workflow 里已预留 `Notify on failure` 步骤，可替换为 Telegram / 企业微信 / Bark webhook。

## 七、备选方案：Playwright（万一后续加了人机校验）

```yaml
- name: Install deps
  run: |
    pip install playwright
    python -m playwright install --with-deps chromium
- name: Check-in via browser
  env:
    A2X_COOKIE: ${{ secrets.A2X_COOKIE }}
  run: python checkin_browser.py
```

`checkin_browser.py` 要点：Cookie 逐条 `context.add_cookies()` 注入（`__Host-` 前缀要求 `secure=True`、`path="/"`、不填 domain），
打开 `/growth`，`page.click('form.daily-checkin button:not([disabled])')`，等导航完成后判断文案。

## 八、频率建议

本方案每天 1~2 次，属于正常访问量级。
