// First-party synthetic/no-secret preview. Not network isolation.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, extname } from 'node:path';
export const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const catalog = JSON.parse(await readFile(resolve(root, 'i18n/strings.json'), 'utf8'));
export const routes = page => Object.keys(catalog.languages).map(code => `/web/${page}?lang=${encodeURIComponent(code)}`);
const beacon = `<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "1866ec8651e049d5a1f7336759a128fd"}'></script>`;
const mime = { '.html': 'text/html', '.js': 'application/javascript', '.png': 'image/png' };
export async function serve(port = 0) {
  const server = createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      if (pathname.startsWith('/docs/images/') && /^\/docs\/images\/step[1-6]\.png$/.test(pathname)) {
        // Guide screenshots are excluded, not copied from account walkthroughs.
        const sizes = { step1: [2828, 330], step2: [2838, 1498], step3: [554, 1148], step4: [1120, 1156], step5: [1102, 1462], step6: [1062, 370] };
        const [width, height] = sizes[pathname.split('/').pop().split('.')[0]];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="${width}" height="${height}" fill="#fff"/><text x="20" y="40" fill="#111">ZZ synthetic guide image</text></svg>`;
        res.writeHead(200, { 'content-type': 'image/svg+xml' }); res.end(svg); return;
      }
      if (!/^\/web\/[a-zA-Z0-9_-]+\.(html|js|png)$/.test(pathname)) throw new Error('path');
      let body = await readFile(resolve(root, '.' + pathname));
      if (extname(pathname) === '.html') {
        const html = body.toString('utf8');
        if (html.split(beacon).length !== 2) throw new Error('beacon changed');
        body = html.replace(beacon, '');
      }
      res.writeHead(200, { 'content-type': mime[extname(pathname)] }); res.end(body);
    } catch { res.writeHead(404); res.end('Synthetic preview unavailable'); }
  });
  await new Promise(resolve => server.listen(port, '127.0.0.1', resolve));
  return { server, base: `http://127.0.0.1:${server.address().port}/` };
}
if (process.argv[2] === 'preview') {
  await serve(8765);
  const { writeFile } = await import('node:fs/promises');
  await writeFile(resolve(root, '.a11y-routes.json'), JSON.stringify({ version: 1, paths: [...routes('index.html'), ...routes('guide.html')] }));
  console.log('Synthetic accessibility preview ready');
}
