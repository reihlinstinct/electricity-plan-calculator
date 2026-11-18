// Minimal XLSX writer, no dependencies: an uncompressed ZIP holding a workbook
// with inline-string/number cells, right-to-left sheet views and optional PNG
// images anchored to a cell. Everything is built in memory in the browser;
// nothing is sent anywhere.
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function zipStore(entries) {
  // entries: [{name, data: Uint8Array}]
  const chunks = [];
  const central = [];
  let offset = 0;
  const push = arr => { chunks.push(arr); offset += arr.length; };
  const u16 = v => new Uint8Array([v & 0xff, (v >>> 8) & 0xff]);
  const u32 = v => new Uint8Array([v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff]);
  for (const e of entries) {
    const name = new TextEncoder().encode(e.name);
    const crc = crc32(e.data);
    const local = [u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(0), u16(0),
      u32(crc), u32(e.data.length), u32(e.data.length), u16(name.length), u16(0), name];
    const localOffset = offset;
    local.forEach(push);
    push(e.data);
    central.push([u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0),
      u32(crc), u32(e.data.length), u32(e.data.length), u16(name.length), u16(0), u16(0),
      u16(0), u16(0), u32(0), u32(localOffset), name]);
  }
  const cdStart = offset;
  for (const c of central) c.forEach(push);
  const cdSize = offset - cdStart;
  [u32(0x06054b50), u16(0), u16(0), u16(entries.length), u16(entries.length),
    u32(cdSize), u32(cdStart), u16(0)].forEach(push);
  const out = new Uint8Array(offset);
  let pos = 0;
  for (const c of chunks) { out.set(c, pos); pos += c.length; }
  return out;
}

const xmlEscape = s => String(s)
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;');

const colLetter = i => {
  let s = '';
  i++;
  while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = (i - m - 1) / 26; }
  return s;
};

function sheetXml(sheet) {
  const rows = sheet.rows.map((row, r) => {
    const cells = row.map((cell, c) => {
      const ref = colLetter(c) + (r + 1);
      if (cell == null) return '';
      if (typeof cell === 'number' && Number.isFinite(cell)) {
        return `<c r="${ref}"><v>${cell}</v></c>`;
      }
      return `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${xmlEscape(cell)}</t></is></c>`;
    }).join('');
    return `<row r="${r + 1}">${cells}</row>`;
  }).join('');
  const drawing = sheet.image ? '<drawing r:id="rId1"/>' : '';
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    + '<sheetViews><sheetView workbookViewId="0" rightToLeft="1"/></sheetViews>'
    + `<sheetData>${rows}</sheetData>${drawing}</worksheet>`;
}

function drawingXml(image) {
  const cx = image.width * 9525, cy = image.height * 9525;
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
    + 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    + '<xdr:oneCellAnchor><xdr:from>'
    + `<xdr:col>${image.col || 0}</xdr:col><xdr:colOff>0</xdr:colOff>`
    + `<xdr:row>${image.row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>`
    + `<xdr:ext cx="${cx}" cy="${cy}"/>`
    + '<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="chart"/><xdr:cNvPicPr/></xdr:nvPicPr>'
    + '<xdr:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
    + '<xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic>'
    + '<xdr:clientData/></xdr:oneCellAnchor></xdr:wsDr>';
}

const sheetName = (name, i) => {
  const clean = String(name).replace(/[\\/*?:[\]]/g, ' ').trim() || 'Sheet';
  return (clean.slice(0, 28) || 'Sheet') + (i ? '' : '');
};

// sheets: [{name, rows: [[string|number|null, ...]], image?: {png: Uint8Array, width, height, row, col?}}]
export function buildXlsx(sheets) {
  const entries = [];
  const enc = s => new TextEncoder().encode(s);
  const types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
    '<Default Extension="xml" ContentType="application/xml"/>',
    '<Default Extension="png" ContentType="image/png"/>',
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'];
  sheets.forEach((_, i) => types.push(
    `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`));
  let drawings = 0;
  sheets.forEach((s, i) => {
    if (s.image) {
      drawings++;
      types.push(`<Override PartName="/xl/drawings/drawing${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>`);
    }
  });
  types.push('</Types>');
  entries.push({ name: '[Content_Types].xml', data: enc(types.join('')) });

  entries.push({ name: '_rels/.rels', data: enc('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    + '</Relationships>') });

  const sheetTags = sheets.map((s, i) =>
    `<sheet name="${xmlEscape(sheetName(s.name, i))}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('');
  entries.push({ name: 'xl/workbook.xml', data: enc('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    + `<sheets>${sheetTags}</sheets></workbook>`) });

  const wbRels = sheets.map((s, i) =>
    `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('');
  entries.push({ name: 'xl/_rels/workbook.xml.rels', data: enc('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${wbRels}</Relationships>`) });

  let imageIndex = 0;
  sheets.forEach((s, i) => {
    entries.push({ name: `xl/worksheets/sheet${i + 1}.xml`, data: enc(sheetXml(s)) });
    if (s.image) {
      imageIndex++;
      entries.push({ name: `xl/worksheets/_rels/sheet${i + 1}.xml.rels`, data: enc('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing${i + 1}.xml"/>`
        + '</Relationships>') });
      entries.push({ name: `xl/drawings/drawing${i + 1}.xml`, data: enc(drawingXml(s.image)) });
      entries.push({ name: `xl/drawings/_rels/drawing${i + 1}.xml.rels`, data: enc('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image${imageIndex}.png"/>`
        + '</Relationships>') });
      entries.push({ name: `xl/media/image${imageIndex}.png`, data: s.image.png });
    }
  });
  return zipStore(entries);
}

// data:image/png;base64,... -> Uint8Array
export function pngFromCanvas(canvas) {
  const b64 = canvas.toDataURL('image/png').split(',')[1];
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return { png: out, width: canvas.width, height: canvas.height };
}

export function downloadXlsx(bytes, filename) {
  const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
