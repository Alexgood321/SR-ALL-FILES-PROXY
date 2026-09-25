/*
 * Spotify lyrics translator for Shadowrocket
 *
 * Локальная реализация для SR-ALL-FILES-PROXY.
 * Идея функции основана на публичном модуле app2smile/rules, но этот файл
 * не загружает и не исполняет код из сторонних репозиториев.
 *
 * Важно:
 *   - скрипт выключен в модуле по умолчанию;
 *   - при включении отправляет текст песни в официальный Baidu Translate API;
 *   - секрет Baidu не отправляется напрямую: он используется локально для MD5-подписи;
 *   - других внешних HTTP-запросов нет.
 */

(() => {
  'use strict';

  function bytesOf(value) {
    if (value instanceof Uint8Array) return value;
    if (value instanceof ArrayBuffer) return new Uint8Array(value);
    if (value && value.buffer instanceof ArrayBuffer) {
      return new Uint8Array(value.buffer, value.byteOffset || 0, value.byteLength || value.length);
    }
    throw new TypeError('Ожидалось бинарное тело ответа');
  }

  function utf8Encode(text) {
    const out = [];
    for (const ch of String(text)) {
      const cp = ch.codePointAt(0);
      if (cp <= 0x7f) out.push(cp);
      else if (cp <= 0x7ff) {
        out.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
      } else if (cp <= 0xffff) {
        out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
      } else {
        out.push(
          0xf0 | (cp >> 18),
          0x80 | ((cp >> 12) & 0x3f),
          0x80 | ((cp >> 6) & 0x3f),
          0x80 | (cp & 0x3f),
        );
      }
    }
    return Uint8Array.from(out);
  }

  function utf8Decode(bytes) {
    let out = '';
    for (let i = 0; i < bytes.length;) {
      const b0 = bytes[i++];
      if (b0 < 0x80) out += String.fromCodePoint(b0);
      else if ((b0 & 0xe0) === 0xc0 && i < bytes.length) {
        const b1 = bytes[i++];
        out += String.fromCodePoint(((b0 & 0x1f) << 6) | (b1 & 0x3f));
      } else if ((b0 & 0xf0) === 0xe0 && i + 1 < bytes.length) {
        const b1 = bytes[i++];
        const b2 = bytes[i++];
        out += String.fromCodePoint(((b0 & 0x0f) << 12) | ((b1 & 0x3f) << 6) | (b2 & 0x3f));
      } else if ((b0 & 0xf8) === 0xf0 && i + 2 < bytes.length) {
        const b1 = bytes[i++];
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        out += String.fromCodePoint(
          ((b0 & 0x07) << 18) | ((b1 & 0x3f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f),
        );
      } else out += '\uFFFD';
    }
    return out;
  }

  function readVarint(bytes, start) {
    let value = 0n;
    let shift = 0n;
    let pos = start;
    while (pos < bytes.length) {
      const b = BigInt(bytes[pos++]);
      value |= (b & 0x7fn) << shift;
      if ((b & 0x80n) === 0n) return { value, pos };
      shift += 7n;
      if (shift > 70n) throw new Error('Некорректный protobuf varint');
    }
    throw new Error('Оборванный protobuf varint');
  }

  function encodeVarint(input) {
    let value = BigInt(input);
    if (value < 0n) value = BigInt.asUintN(64, value);
    const out = [];
    do {
      let b = Number(value & 0x7fn);
      value >>= 7n;
      if (value !== 0n) b |= 0x80;
      out.push(b);
    } while (value !== 0n);
    return Uint8Array.from(out);
  }

  function concatBytes(chunks) {
    const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const out = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) {
      out.set(chunk, offset);
      offset += chunk.length;
    }
    return out;
  }

  function parseMessage(bytes) {
    const fields = [];
    let pos = 0;
    while (pos < bytes.length) {
      const tag = readVarint(bytes, pos);
      pos = tag.pos;
      const no = Number(tag.value >> 3n);
      const wire = Number(tag.value & 7n);
      if (wire === 0) {
        const v = readVarint(bytes, pos);
        pos = v.pos;
        fields.push({ no, wire, value: v.value });
      } else if (wire === 1) {
        if (pos + 8 > bytes.length) throw new Error('Оборванный protobuf fixed64');
        fields.push({ no, wire, value: bytes.slice(pos, pos + 8) });
        pos += 8;
      } else if (wire === 2) {
        const len = readVarint(bytes, pos);
        pos = len.pos;
        const size = Number(len.value);
        if (!Number.isSafeInteger(size) || pos + size > bytes.length) throw new Error('Некорректная длина protobuf');
        fields.push({ no, wire, value: bytes.slice(pos, pos + size) });
        pos += size;
      } else if (wire === 5) {
        if (pos + 4 > bytes.length) throw new Error('Оборванный protobuf fixed32');
        fields.push({ no, wire, value: bytes.slice(pos, pos + 4) });
        pos += 4;
      } else {
        throw new Error(`Неподдерживаемый protobuf wire type: ${wire}`);
      }
    }
    return fields;
  }

  function encodeMessage(fields) {
    const chunks = [];
    for (const field of fields) {
      chunks.push(encodeVarint((BigInt(field.no) << 3n) | BigInt(field.wire)));
      if (field.wire === 0) chunks.push(encodeVarint(field.value));
      else if (field.wire === 2) chunks.push(encodeVarint(field.value.length), field.value);
      else chunks.push(field.value);
    }
    return concatBytes(chunks);
  }

  function lengthFields(fields, no) {
    return fields.filter((field) => field.no === no && field.wire === 2);
  }

  function firstLengthField(fields, no) {
    return fields.find((field) => field.no === no && field.wire === 2);
  }

  function parseArgs() {
    const out = { appid: '', securityKey: '' };
    if (typeof $argument !== 'string') return out;
    for (const item of $argument.split('&')) {
      const eq = item.indexOf('=');
      const key = eq === -1 ? item : item.slice(0, eq);
      const value = eq === -1 ? '' : item.slice(eq + 1);
      if (key === 'appid') out.appid = decodeURIComponent(value);
      if (key === 'securityKey') out.securityKey = decodeURIComponent(value);
    }
    return out;
  }

  function rol(value, bits) {
    return ((value << bits) | (value >>> (32 - bits))) >>> 0;
  }

  function md5(text) {
    const source = Array.from(utf8Encode(text));
    const bitLength = BigInt(source.length) * 8n;
    source.push(0x80);
    while ((source.length % 64) !== 56) source.push(0);
    for (let i = 0; i < 8; i++) source.push(Number((bitLength >> BigInt(i * 8)) & 0xffn));

    let a0 = 0x67452301;
    let b0 = 0xefcdab89;
    let c0 = 0x98badcfe;
    let d0 = 0x10325476;

    const shifts = [
      7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
      5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
      4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
      6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
    ];
    const constants = Array.from({ length: 64 }, (_, i) =>
      Math.floor(Math.abs(Math.sin(i + 1)) * 0x100000000) >>> 0,
    );

    for (let offset = 0; offset < source.length; offset += 64) {
      const words = new Uint32Array(16);
      for (let i = 0; i < 16; i++) {
        const p = offset + i * 4;
        words[i] = (
          source[p] |
          (source[p + 1] << 8) |
          (source[p + 2] << 16) |
          (source[p + 3] << 24)
        ) >>> 0;
      }

      let a = a0;
      let b = b0;
      let c = c0;
      let d = d0;

      for (let i = 0; i < 64; i++) {
        let f;
        let g;
        if (i < 16) {
          f = (b & c) | (~b & d);
          g = i;
        } else if (i < 32) {
          f = (d & b) | (~d & c);
          g = (5 * i + 1) % 16;
        } else if (i < 48) {
          f = b ^ c ^ d;
          g = (3 * i + 5) % 16;
        } else {
          f = c ^ (b | ~d);
          g = (7 * i) % 16;
        }

        const nextD = c;
        c = b;
        const sum = (a + f + constants[i] + words[g]) >>> 0;
        b = (b + rol(sum, shifts[i])) >>> 0;
        a = d;
        d = nextD;
      }

      a0 = (a0 + a) >>> 0;
      b0 = (b0 + b) >>> 0;
      c0 = (c0 + c) >>> 0;
      d0 = (d0 + d) >>> 0;
    }

    const hex = (word) => {
      let out = '';
      for (let i = 0; i < 4; i++) out += ((word >>> (i * 8)) & 0xff).toString(16).padStart(2, '0');
      return out;
    };
    return hex(a0) + hex(b0) + hex(c0) + hex(d0);
  }

  function postForm(url, body) {
    const request = {
      url,
      body,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
    };

    if (typeof $httpClient !== 'undefined') {
      return new Promise((resolve, reject) => {
        $httpClient.post(request, (error, response, data) => {
          if (error) reject(error);
          else resolve({ status: Number(response.status || response.statusCode || 0), data });
        });
      });
    }

    if (typeof $task !== 'undefined') {
      return $task.fetch({ ...request, method: 'POST' }).then((response) => ({
        status: Number(response.statusCode || response.status || 0),
        data: response.body,
      }));
    }

    return Promise.reject(new Error('HTTP API среды Shadowrocket недоступен'));
  }

  function parseColorLyrics(body) {
    const root = parseMessage(body);
    const lyricsField = firstLengthField(root, 1);
    if (!lyricsField) throw new Error('В ответе Spotify отсутствует поле lyrics');

    const lyrics = parseMessage(lyricsField.value);
    const languageField = firstLengthField(lyrics, 10);
    const language = languageField ? utf8Decode(languageField.value) : '';
    const lines = lengthFields(lyrics, 2).map((lineField) => {
      const line = parseMessage(lineField.value);
      const words = firstLengthField(line, 2);
      return words ? utf8Decode(words.value) : '';
    });

    return { root, lyricsField, lyrics, language, lines };
  }

  function buildAlternative(language, lines) {
    const fields = [{ no: 1, wire: 2, value: utf8Encode(language) }];
    for (const line of lines) fields.push({ no: 2, wire: 2, value: utf8Encode(line) });
    return encodeMessage(fields);
  }

  async function main() {
    const status = Number($response.status || $response.statusCode || 200);
    if (status !== 200) return $done({});

    const { appid, securityKey } = parseArgs();
    if (!appid || !securityKey || appid === 'не_задан' || securityKey === 'не_задан') {
      console.log('[Spotify SR-ALL] Перевод включён, но AppID/ключ Baidu не заданы');
      return $done({});
    }

    const parsed = parseColorLyrics(bytesOf($response.body));
    if (!parsed.language || parsed.language === 'z1' || parsed.lines.length === 0) return $done({});

    const unique = parsed.lines
      .filter((line) => line && line !== '♪')
      .filter((line, index, array) => array.indexOf(line) === index);
    if (unique.length === 0) return $done({});

    const query = unique.join('\n');
    const salt = String(Date.now());
    const sign = md5(appid + query + salt + securityKey);
    const body = [
      ['q', query],
      ['from', 'auto'],
      ['to', 'zh'],
      ['appid', appid],
      ['salt', salt],
      ['sign', sign],
    ].map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('&');

    const response = await postForm('https://fanyi-api.baidu.com/api/trans/vip/translate', body);
    if (response.status !== 200) throw new Error(`Baidu Translate HTTP ${response.status}`);

    const payload = JSON.parse(response.data || '{}');
    if (payload.error_code && String(payload.error_code) !== '52000') {
      throw new Error(`Baidu Translate error ${payload.error_code}: ${payload.error_msg || 'unknown'}`);
    }

    const translationMap = new Map();
    for (const item of payload.trans_result || []) {
      if (item && typeof item.src === 'string' && typeof item.dst === 'string' && item.src !== item.dst) {
        translationMap.set(item.src, item.dst);
      }
    }

    const translatedLines = parsed.lines.map((line) => translationMap.get(line) || line || '');
    parsed.lyrics = parsed.lyrics.filter((field) => field.no !== 9);
    parsed.lyrics.push({ no: 9, wire: 2, value: buildAlternative('z1', translatedLines) });
    parsed.lyricsField.value = encodeMessage(parsed.lyrics);

    $done({ body: encodeMessage(parsed.root) });
  }

  main().catch((error) => {
    console.log(`[Spotify SR-ALL Lyrics] ${error && error.stack ? error.stack : error}`);
    $done({});
  });
})();
