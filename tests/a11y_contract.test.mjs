import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { serve, routes, root, catalog } from './a11y-preview.mjs';

test('every page discovers its languages from the catalog, within route limits', () => {
  for (const page of ['index.html', 'guide.html', 'sources.html']) {
    const paths = routes(page);
    assert.equal(paths.length, Object.keys(catalog.languages).length);
    for (const path of paths) {
      const url = new URL(path, 'http://127.0.0.1');
      assert.equal(url.pathname, `/web/${page}`);
      assert.ok(Object.hasOwn(catalog.languages, url.searchParams.get('lang')));
    }
  }
  assert.ok(routes('index.html').length + routes('guide.html').length <= 12);
});

test('preview binds loopback, strips only the exact beacon and substitutes guide images', async () => {
  const { server, base } = await serve();
  try {
    assert.equal(server.address().address, '127.0.0.1');
    for (const page of ['index.html', 'guide.html', 'sources.html']) {
      const response = await fetch(base + 'web/' + page);
      assert.equal(response.status, 200);
      const source = await readFile(resolve(root, 'web', page), 'utf8');
      const beacon = source.split('\n').find(line => line.startsWith('<script type="module" src="https://static.cloudflareinsights.com/'));
      assert.ok(beacon);
      assert.equal(await response.text(), source.replace(beacon, ''));
    }
    const image = await fetch(base + 'docs/images/step4.png');
    assert.equal(image.headers.get('content-type'), 'image/svg+xml');
    const body = await image.text();
    assert.match(body, /width="1120" height="1156"/);
    assert.match(body, /ZZ synthetic/);
    assert.equal((await fetch(base + 'data/sample_consumption.csv')).status, 404);
    assert.equal((await fetch(base + 'ACCESSIBILITY.md')).status, 404);
  } finally { server.closeAllConnections(); server.close(); }
});
