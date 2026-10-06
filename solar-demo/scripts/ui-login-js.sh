#!/usr/bin/env bash
# ui-login-js.sh <роль> <url-path> — генерирует .private/ui_login.js (cookie сессии → Playwright)
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"
SID=$(awk '$6=="session_id"{print $7}' "$D/.private/$1.cookies")
cat > "$D/.private/ui_login.js" <<JS
async (page0) => {
  // свежий контекст: пустой IndexedDB/RPC-кеш веб-клиента, как у нового входа
  const ctx = await page0.context().browser().newContext({viewport: {width: 1400, height: 900}});
  const page = await ctx.newPage();
  globalThis.__solarPage = page;
  await ctx.addCookies([{name: 'session_id', value: '$SID', domain: 'localhost', path: '/', httpOnly: true}]);
  await page.goto('http://localhost:8069$2'); await page.waitForTimeout(4000);
  const btns = await page.evaluate(() => [...document.querySelectorAll('.o_statusbar_buttons button')].filter(b=>b.offsetParent).map(b => b.innerText.trim()));
  return {url: page.url(), title: await page.title(), btns, text: (await page.evaluate(() => document.body.innerText)).replace(/\s+/g,' ').slice(0, 300)};
}
JS
chmod 600 "$D/.private/ui_login.js"
