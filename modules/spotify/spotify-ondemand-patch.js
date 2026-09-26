// LOCAL PATCH — Spotify OnDemand Selector A/B patch.
// Purpose: test whether Spotify's server-provided OnDemand URI set is the
// mechanism behind the observed seek -> next-track behavior for one known
// problematic playlist context.
//
// Known protobuf shape (OndemandResponse):
//   field 1: repeated string uris
//   field 2: int64 expireTimestampMillis
//
// LOCAL PATCH SAFETY / SCOPE:
//   - touches only /ondemand-selector/v2/select-ondemand-set responses
//   - preserves Spotify's original protobuf bytes byte-for-byte
//   - if the target URI is absent, appends ONE additional field-1 string
//   - does not rewrite/remove any existing URI or expiry/unknown field
//   - on parse/encoding failure, returns the original response unchanged

(() => {
  const TAG = "[Spotify OnDemand Patch]";
  const TARGET_URI = "spotify:playlist:37i9dQZF1E4o26widVLGBM";

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

  function encodeVarint(value) {
    if (!Number.isSafeInteger(value) || value < 0) throw new Error("invalid varint value");
    const out = [];
    let n = value;

    while (n >= 0x80) {
      out.push((n % 128) | 0x80);
      n = Math.floor(n / 128);
    }
    out.push(n);
    return out;
  }

  function decodeUtf8(bytes, start, length) {
    const end = start + length;
    let out = "";

    for (let i = start; i < end;) {
      const b1 = bytes[i++];
      if (b1 < 0x80) {
        out += String.fromCharCode(b1);
      } else if ((b1 & 0xe0) === 0xc0 && i < end) {
        const b2 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x1f) << 6) | (b2 & 0x3f));
      } else if ((b1 & 0xf0) === 0xe0 && i + 1 < end) {
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x0f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f));
      } else if ((b1 & 0xf8) === 0xf0 && i + 2 < end) {
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        const b4 = bytes[i++];
        let cp = ((b1 & 0x07) << 18) | ((b2 & 0x3f) << 12) | ((b3 & 0x3f) << 6) | (b4 & 0x3f);
        cp -= 0x10000;
        out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
      } else {
        out += "�";
      }
    }

    return out;
  }

  function encodeUtf8(text) {
    const out = [];

    for (let i = 0; i < text.length; i++) {
      let cp = text.charCodeAt(i);

      if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < text.length) {
        const low = text.charCodeAt(i + 1);
        if (low >= 0xdc00 && low <= 0xdfff) {
          cp = 0x10000 + ((cp - 0xd800) << 10) + (low - 0xdc00);
          i++;
        }
      }

      if (cp < 0x80) {
        out.push(cp);
      } else if (cp < 0x800) {
        out.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
      } else if (cp < 0x10000) {
        out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
      } else {
        out.push(
          0xf0 | (cp >> 18),
          0x80 | ((cp >> 12) & 0x3f),
          0x80 | ((cp >> 6) & 0x3f),
          0x80 | (cp & 0x3f)
        );
      }
    }

    return new Uint8Array(out);
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
    const original = toBytes($response.body);
    if (!original) {
      console.log(`${TAG} unable to read binary response body; passthrough`);
      $done({});
      return;
    }

    // LOCAL PATCH: inspect only enough protobuf structure to determine whether
    // TARGET_URI already exists. Original bytes are never reconstructed.
    const state = { pos: 0 };
    let uriCount = 0;
    let targetPresent = false;

    while (state.pos < original.length) {
      const key = readVarint(original, state);
      const fieldNumber = Math.floor(key / 8);
      const wireType = key & 0x07;

      if (fieldNumber === 1 && wireType === 2) {
        const length = readVarint(original, state);
        if (state.pos + length > original.length) throw new Error("URI exceeds response length");
        const uri = decodeUtf8(original, state.pos, length);
        uriCount++;
        if (uri === TARGET_URI) targetPresent = true;
        state.pos += length;
        continue;
      }

      skipField(original, state, wireType);
      if (state.pos > original.length) throw new Error("field exceeds response length");
    }

    if (targetPresent) {
      console.log(`${TAG} target already present; uris=${uriCount}; passthrough`);
      $done({});
      return;
    }

    // LOCAL PATCH: append one legal protobuf occurrence of field 1 (wire type 2).
    // Existing bytes remain byte-identical and in the same order.
    const uriBytes = encodeUtf8(TARGET_URI);
    const lengthBytes = encodeVarint(uriBytes.length);
    const extraLength = 1 + lengthBytes.length + uriBytes.length;
    const patched = new Uint8Array(original.length + extraLength);

    patched.set(original, 0);
    let p = original.length;
    patched[p++] = 0x0a; // field 1, wire type 2
    patched.set(lengthBytes, p);
    p += lengthBytes.length;
    patched.set(uriBytes, p);

    console.log(
      `${TAG} target appended; uris=${uriCount}->${uriCount + 1}; ` +
      `bytes=${original.length}->${patched.length}; target=${TARGET_URI}`
    );

    $done({ body: patched });
  } catch (error) {
    console.log(`${TAG} patch error: ${error && error.message ? error.message : error}; passthrough`);
    $done({});
  }
})();
