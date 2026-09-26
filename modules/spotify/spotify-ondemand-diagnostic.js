// LOCAL PATCH — Spotify OnDemand Selector diagnostic.
// Purpose: inspect Spotify's protobuf response from
// /ondemand-selector/v2/select-ondemand-set without changing it.
//
// Known protobuf shape (OndemandResponse):
//   field 1: repeated string uris
//   field 2: int64 expireTimestampMillis
//
// IMPORTANT: this script is diagnostic-only. It logs decoded values and then
// calls $done({}) so Shadowrocket forwards Spotify's original response unchanged.

(() => {
  const TAG = "[Spotify OnDemand Diagnostic]";
  const KNOWN_PROBLEM_CONTEXT = "spotify:playlist:37i9dQZF1E4o26widVLGBM";
  const MAX_URI_LOGS = 40;

  function toBytes(body) {
    if (!body) return null;

    if (typeof Uint8Array !== "undefined" && body instanceof Uint8Array) {
      return body;
    }

    if (typeof ArrayBuffer !== "undefined" && body instanceof ArrayBuffer) {
      return new Uint8Array(body);
    }

    if (body.buffer && typeof ArrayBuffer !== "undefined" && body.buffer instanceof ArrayBuffer) {
      const offset = body.byteOffset || 0;
      const length = body.byteLength != null ? body.byteLength : body.length;
      return new Uint8Array(body.buffer, offset, length);
    }

    return null;
  }

  function readVarint(bytes, state) {
    let value = 0;
    let factor = 1;

    for (let i = 0; i < 10; i++) {
      if (state.pos >= bytes.length) throw new Error("unexpected EOF while reading varint");
      const b = bytes[state.pos++];
      value += (b & 0x7f) * factor;
      if ((b & 0x80) === 0) return value;
      factor *= 128;
    }

    throw new Error("invalid varint");
  }

  function decodeUtf8(bytes, start, length) {
    const end = start + length;
    let out = "";

    for (let i = start; i < end;) {
      const b1 = bytes[i++];

      if (b1 < 0x80) {
        out += String.fromCharCode(b1);
        continue;
      }

      if ((b1 & 0xe0) === 0xc0 && i < end) {
        const b2 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x1f) << 6) | (b2 & 0x3f));
        continue;
      }

      if ((b1 & 0xf0) === 0xe0 && i + 1 < end) {
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x0f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f));
        continue;
      }

      if ((b1 & 0xf8) === 0xf0 && i + 2 < end) {
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        const b4 = bytes[i++];
        let cp = ((b1 & 0x07) << 18) | ((b2 & 0x3f) << 12) | ((b3 & 0x3f) << 6) | (b4 & 0x3f);
        cp -= 0x10000;
        out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
        continue;
      }

      out += "�";
    }

    return out;
  }

  function skipField(bytes, state, wireType) {
    switch (wireType) {
      case 0:
        readVarint(bytes, state);
        return;
      case 1:
        state.pos += 8;
        return;
      case 2: {
        const length = readVarint(bytes, state);
        state.pos += length;
        return;
      }
      case 5:
        state.pos += 4;
        return;
      default:
        throw new Error(`unsupported wire type ${wireType}`);
    }
  }

  try {
    // Shadowrocket exposes binary response data through $response.body when
    // binary-body-mode=1. We only read it; the original bytes are not replaced.
    const bytes = toBytes($response.body);
    if (!bytes) {
      console.log(`${TAG} unable to read binary response body`);
      $done({});
      return;
    }

    const state = { pos: 0 };
    const uris = [];
    let expireTimestampMillis = null;
    let unknownFields = 0;

    while (state.pos < bytes.length) {
      const key = readVarint(bytes, state);
      const fieldNumber = Math.floor(key / 8);
      const wireType = key & 0x07;

      if (fieldNumber === 1 && wireType === 2) {
        const length = readVarint(bytes, state);
        if (state.pos + length > bytes.length) throw new Error("URI exceeds response length");
        uris.push(decodeUtf8(bytes, state.pos, length));
        state.pos += length;
        continue;
      }

      if (fieldNumber === 2 && wireType === 0) {
        expireTimestampMillis = readVarint(bytes, state);
        continue;
      }

      unknownFields++;
      skipField(bytes, state, wireType);
      if (state.pos > bytes.length) throw new Error("field exceeds response length");
    }

    const typeCounts = {};
    for (const uri of uris) {
      const match = /^spotify:([^:]+)/.exec(uri);
      const type = match ? match[1] : "other";
      typeCounts[type] = (typeCounts[type] || 0) + 1;
    }

    const targetPresent = uris.indexOf(KNOWN_PROBLEM_CONTEXT) !== -1;
    const expiryIso = expireTimestampMillis != null && isFinite(expireTimestampMillis)
      ? new Date(expireTimestampMillis).toISOString()
      : "n/a";

    console.log(
      `${TAG} bytes=${bytes.length}; uris=${uris.length}; unknownFields=${unknownFields}; ` +
      `expires=${expireTimestampMillis == null ? "n/a" : expireTimestampMillis}; expiryIso=${expiryIso}; ` +
      `knownProblemContextPresent=${targetPresent}`
    );
    console.log(`${TAG} uriTypes=${JSON.stringify(typeCounts)}`);

    const limit = Math.min(uris.length, MAX_URI_LOGS);
    for (let i = 0; i < limit; i++) {
      console.log(`${TAG} uri[${i}]=${uris[i]}`);
    }
    if (uris.length > limit) {
      console.log(`${TAG} ... omitted ${uris.length - limit} URI(s)`);
    }
  } catch (error) {
    console.log(`${TAG} parse error: ${error && error.message ? error.message : error}`);
  }

  // LOCAL PATCH safety property: do not provide a replacement body/response.
  // Shadowrocket therefore forwards the exact original Spotify response.
  $done({});
})();
