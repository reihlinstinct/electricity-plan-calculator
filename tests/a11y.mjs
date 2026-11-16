// Shared trusted browser tools; fixed-schema results, no document contents.
import { pathToFileURL } from 'node:url';
import { resolve, isAbsolute } from 'node:path';
import { serve, routes } from './a11y-preview.mjs';
const tools = process.env.A11Y_TOOLS;
if (!tools || !isAbsolute(tools)) throw new Error('tool path');
const { scan, TAGS, summarize } = await import(pathToFileURL(resolve(tools, 'scan.mjs')));
const axe = (await import(pathToFileURL(resolve(tools, 'node_modules/axe-core/axe.js')))).default;
const { server, base } = await serve();
let errors = false;
const states = [];
try {
  for (const paths of [[...routes('index.html'), ...routes('guide.html')], routes('sources.html')]) {
    const result = await scan(base, { version: 1, paths }, { inspect: async (page, report) => {
      if (!new URL(page.url()).pathname.endsWith('/index.html')) return;
      let failed = false;
      page.on('request', request => { if (new URL(request.url()).origin !== new URL(base).origin) failed = true; });
      page.on('pageerror', () => { failed = true; });
      page.on('response', response => { if (response.status() >= 400) failed = true; });
      await page.routeWebSocket('**/*', socket => { failed = true; socket.close(); });
      const csv = Array.from({ length: 96 }, (_, index) => `1-1,צריכה,02/10/2026,${String(Math.floor(index / 4)).padStart(2, '0')}:${String(index % 4 * 15).padStart(2, '0')},0.5,0`).join('\n');
      await page.locator('#csv').setInputFiles({ name: 'zz-synthetic.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
      await page.click('#go');
      await page.waitForSelector('#plansTable tr');
      await page.addScriptTag({ content: axe.source });
      const findings = await page.evaluate(tags => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }), TAGS);
      if (failed || new URL(page.url()).origin !== new URL(base).origin) throw new Error('interaction failed');
      states.push({ engine: report.engine, width: report.width, page: report.page, state: 'calculation', ...summarize(findings) });
      if (process.env.A11Y_SCREENSHOT && report.engine === 'chromium' && report.page === 1 && report.width === 390) await page.screenshot({ path: process.env.A11Y_SCREENSHOT, fullPage: true });
    } });
    console.log(JSON.stringify(result));
    errors ||= result.status !== 'pass';
  }
  console.log(JSON.stringify({ scope: 'automated-only', states }));
  if (errors || states.some(state => state.violations)) process.exitCode = 1;
} catch {
  console.log('{"schema_version":1,"status":"error","scope":"automated-only"}');
  process.exitCode = 2;
} finally { server.close(); }
