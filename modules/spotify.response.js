/*
 * Spotify response patcher for Shadowrocket
 *
 * Локальная реализация для SR-ALL-FILES-PROXY.
 * Поведение собрано по публичным правилам/идеям LOWERTOP и 001ProMax,
 * но этот файл не загружает и не исполняет код из сторонних репозиториев.
 *
 * Upstream references:
 *   LOWERTOP/Shadowrocket-First
 *   001ProMax/Surge
 *
 * Назначение:
 *   - обработать Spotify user-customization-service / bootstrap protobuf;
 *   - локально изменить client-side account attributes;
 *   - при включённой опции tab скрыть пункт Your Plan в side drawer.
 *
 * Внешних HTTP-запросов этот скрипт не выполняет.
 */

(() => {
  'use strict';

  const PREMIUM_ATTRIBUTES = () => {
    const expiry = new Date();
    expiry.setMonth(expiry.getMonth() + 1);
    const iso = expiry.toISOString().split('.')[0] + 'Z';

    return {
      'subscription-enddate': ['string', iso],
      'product-expiry': ['string', iso],
      'smart-shuffle': ['string', 'AVAILABLE'],
      'is-euterpe': ['bool', true],
      'has-audiobooks-subscription': ['bool', true],
      'type': ['string', 'premium'],
      'payments-initial-campaign': ['string', 'prepaid'],
      'social-session-free-tier': ['bool', false],
      'can_use_superbird': ['bool', true],
      'jam-social-session': ['string', 'EXPANDED'],
      'offline': ['bool', true],
      'audio-quality': ['string', '1'],
      'shuffle-algorithm': ['string', 'RANDOM'],
      'is-thalia': ['bool', true],
      'shuffle': ['bool', false],
      'is-pigeon': ['bool', true],
      'nft-disabled': ['string', '1'],
      'libspotify': ['bool', true],
      'high-bitrate': ['bool', true],
      'unrestricted': ['bool', true],
      'catalogue': ['string', 'premium'],
      'your-library-tags': ['bool', true],
      'ads': ['bool', false],
      'on-demand': ['bool', true],
      'name': ['string', 'Spotify Premium'],
      'loudness-levels': ['string', '1:-5.0,0.0,3.0:-2.0'],
      'social-session': ['bool', true],
      'pick-and-shuffle': ['bool', false],
      'offline-backup': ['string', 'UNRESTRICTED'],
      'lyrics-offline': ['bool', true],
      'streaming-rules': ['string', ''],
      'mixing-tools': ['string', 'EDIT'],
      'mobile': ['bool', true],
      'player-license': ['string', 'premium'],
      'com.spotify.madprops.use.ucs.product.state': ['bool', true],
      'com.spotify.madprops.delivered.by.ucs': ['bool', true],
    };
  };

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
      if (b0 < 0x80) {
        out += String.fromCodePoint(b0);
      } else if ((b0 & 0xe0) === 0xc0 && i < bytes.length) {
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
      } else {
        out += '\uFFFD';
      }
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
      if (no <= 0) throw new Error('Некорректный protobuf field number');

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
        if (!Number.isSafeInteger(size) || size < 0 || pos + size > bytes.length) {
          throw new Error('Некорректная длина protobuf поля');
        }
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
      if (field.wire === 0) {
        chunks.push(encodeVarint(field.value));
      } else if (field.wire === 2) {
        chunks.push(encodeVarint(field.value.length), field.value);
      } else if (field.wire === 1 || field.wire === 5) {
        chunks.push(field.value);
      } else {
        throw new Error(`Неподдерживаемый protobuf wire type: ${field.wire}`);
      }
    }
    return concatBytes(chunks);
  }

  function firstLengthField(fields, no) {
    return fields.find((field) => field.no === no && field.wire === 2);
  }

  function replaceFirstLengthField(fields, no, value) {
    const field = firstLengthField(fields, no);
    if (field) {
      field.value = value;
      return true;
    }
    return false;
  }

  function patchPath(bytes, path, patcher) {
    if (path.length === 0) return patcher(bytes);
    const fields = parseMessage(bytes);
    const field = firstLengthField(fields, path[0]);
    if (!field) return bytes;
    field.value = patchPath(field.value, path.slice(1), patcher);
    return encodeMessage(fields);
  }

  function attributeValue(type, value) {
    if (type === 'bool') {
      return encodeMessage([{ no: 2, wire: 0, value: value ? 1n : 0n }]);
    }
    if (type === 'string') {
      return encodeMessage([{ no: 4, wire: 2, value: utf8Encode(value) }]);
    }
    throw new Error(`Неизвестный тип Spotify attribute: ${type}`);
  }

  function patchMapEntry(entryBytes, key, type, value) {
    const fields = parseMessage(entryBytes);
    const encodedValue = attributeValue(type, value);
    const valueField = firstLengthField(fields, 2);
    if (valueField) valueField.value = encodedValue;
    else fields.push({ no: 2, wire: 2, value: encodedValue });

    if (!firstLengthField(fields, 1)) {
      fields.unshift({ no: 1, wire: 2, value: utf8Encode(key) });
    }
    return encodeMessage(fields);
  }

  function upsertAccountAttribute(accountFields, key, type, value) {
    for (const field of accountFields) {
      if (field.no !== 1 || field.wire !== 2) continue;
      const entryFields = parseMessage(field.value);
      const keyField = firstLengthField(entryFields, 1);
      if (keyField && utf8Decode(keyField.value) === key) {
        field.value = patchMapEntry(field.value, key, type, value);
        return;
      }
    }

    const entry = encodeMessage([
      { no: 1, wire: 2, value: utf8Encode(key) },
      { no: 2, wire: 2, value: attributeValue(type, value) },
    ]);
    accountFields.push({ no: 1, wire: 2, value: entry });
  }

  function patchAccountAttributesSuccess(bytes) {
    const fields = parseMessage(bytes);
    const attributes = PREMIUM_ATTRIBUTES();
    for (const [key, [type, value]] of Object.entries(attributes)) {
      upsertAccountAttribute(fields, key, type, value);
    }
    return encodeMessage(fields);
  }

  function parseArguments() {
    const result = { tab: true };
    if (typeof $argument !== 'string' || !$argument) return result;

    let raw = $argument.trim();
    if (raw.startsWith('{')) {
      try {
        const parsed = JSON.parse(raw);
        if ('tab' in parsed) result.tab = parsed.tab === true || parsed.tab === 'true';
        return result;
      } catch (_) {}
    }

    for (const part of raw.split('&')) {
      const [key, value = ''] = part.split('=', 2);
      if (key === 'tab') result.tab = value === 'true' || value === '1';
    }
    return result;
  }

  function patchAssignedValue(bytes) {
    const fields = parseMessage(bytes);
    const propertyId = firstLengthField(fields, 1);
    if (!propertyId) return bytes;

    const propertyFields = parseMessage(propertyId.value);
    const scopeField = firstLengthField(propertyFields, 1);
    if (!scopeField || utf8Decode(scopeField.value) !== 'ios-system-your-plan-sidedrawer') {
      return bytes;
    }

    const boolValue = firstLengthField(fields, 3);
    if (!boolValue) return bytes;
    const boolFields = parseMessage(boolValue.value);
    const valueField = boolFields.find((field) => field.no === 1 && field.wire === 0);
    if (valueField) valueField.value = 0n;
    else boolFields.push({ no: 1, wire: 0, value: 0n });
    boolValue.value = encodeMessage(boolFields);
    return encodeMessage(fields);
  }

  function patchResolveSuccess(bytes, args) {
    if (!args.tab) return bytes;
    const fields = parseMessage(bytes);
    const configuration = firstLengthField(fields, 1);
    if (!configuration) return bytes;

    const configFields = parseMessage(configuration.value);
    for (const field of configFields) {
      if (field.no === 3 && field.wire === 2) field.value = patchAssignedValue(field.value);
    }
    configuration.value = encodeMessage(configFields);
    return encodeMessage(fields);
  }

  function patchSuccess(bytes, args) {
    const fields = parseMessage(bytes);

    const resolveSuccess = firstLengthField(fields, 1);
    if (resolveSuccess) resolveSuccess.value = patchResolveSuccess(resolveSuccess.value, args);

    const accountAttributesSuccess = firstLengthField(fields, 3);
    if (accountAttributesSuccess) {
      accountAttributesSuccess.value = patchAccountAttributesSuccess(accountAttributesSuccess.value);
    }

    return encodeMessage(fields);
  }

  try {
    const status = Number($response.status || $response.statusCode || 200);
    if (status !== 200) {
      $done({});
      return;
    }

    const url = new URL($request.url);
    const input = bytesOf($response.body);
    const args = parseArguments();
    let output = input;

    if (url.pathname === '/user-customization-service/v1/customize') {
      output = patchPath(input, [1], (bytes) => patchSuccess(bytes, args));
    } else if (url.pathname === '/bootstrap/v1/bootstrap') {
      output = patchPath(input, [2, 1, 1, 1], (bytes) => patchSuccess(bytes, args));
    }

    $done({ body: output });
  } catch (error) {
    console.log(`[Spotify SR-ALL] ${error && error.stack ? error.stack : error}`);
    $done({});
  }
})();
