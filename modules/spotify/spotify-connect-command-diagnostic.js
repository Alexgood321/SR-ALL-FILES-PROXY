// LOCAL PATCH — Spotify Connect player-command diagnostic.
// Purpose: capture the exact command iOS sends when a seek succeeds or turns
// into a next-track transition, without changing the command body.
//
// Scope:
//   - only /connect-state/v1/player/command/* request traffic
//   - decodes gzip JSON for logging when possible
//   - logs endpoint/position/relative/context/track/from/to
//   - also applies the existing Europe/Moscow -> Europe/Helsinki timezone patch
//     because this specific rule must run before the generic timezone rule
//   - never changes request body, auth, cookies, Connect IDs or command payload

(() => {
  const TAG = "[Spotify Command Diagnostic]";
  const FROM_TZ = "Europe/Moscow";
  const TO_TZ = "Europe/Helsinki";

  function getHeader(headers, wanted) {
    const lower = wanted.toLowerCase();
    for (const key of Object.keys(headers || {})) {
      if (key.toLowerCase() === lower) return String(headers[key]);
    }
    return "";
  }

  function toBytes(body) {
    if (body == null) return null;
    if (typeof Uint8Array !== "undefined" && body instanceof Uint8Array) return body;
    if (typeof ArrayBuffer !== "undefined" && body instanceof ArrayBuffer) return new Uint8Array(body);
    if (body.buffer && typeof ArrayBuffer !== "undefined" && body.buffer instanceof ArrayBuffer) {
      const offset = body.byteOffset || 0;
      const length = body.byteLength != null ? body.byteLength : body.length;
      return new Uint8Array(body.buffer, offset, length);
    }
    if (typeof body === "string") {
      const out = new Uint8Array(body.length);
      for (let i = 0; i < body.length; i++) out[i] = body.charCodeAt(i) & 0xff;
      return out;
    }
    return null;
  }

  function decodeUtf8(bytes) {
    if (!bytes) return "";
    let out = "";
    for (let i = 0; i < bytes.length;) {
      const b1 = bytes[i++];
      if (b1 < 0x80) out += String.fromCharCode(b1);
      else if ((b1 & 0xe0) === 0xc0 && i < bytes.length) {
        const b2 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x1f) << 6) | (b2 & 0x3f));
      } else if ((b1 & 0xf0) === 0xe0 && i + 1 < bytes.length) {
        const b2 = bytes[i++], b3 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x0f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f));
      } else if ((b1 & 0xf8) === 0xf0 && i + 2 < bytes.length) {
        const b2 = bytes[i++], b3 = bytes[i++], b4 = bytes[i++];
        let cp = ((b1 & 0x07) << 18) | ((b2 & 0x3f) << 12) | ((b3 & 0x3f) << 6) | (b4 & 0x3f);
        cp -= 0x10000;
        out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
      } else out += "�";
    }
    return out;
  }

  function applyTimezonePatch(url, originalHeaders) {
    const headers = Object.assign({}, originalHeaders || {});
    let headerChanged = false;
    let urlChanged = false;

    for (const key of Object.keys(headers)) {
      if (/^(time-zone|x-client-timezone)$/i.test(key) && String(headers[key]).toLowerCase() === FROM_TZ.toLowerCase()) {
        headers[key] = TO_TZ;
        headerChanged = true;
      }
    }

    const replaceParam = (input, name) => {
      const re = new RegExp(`([?&])${name}=Europe(?:%2F|/)Moscow(?=(&|$))`, "gi");
      const output = input.replace(re, `$1${name}=Europe%2FHelsinki`);
      if (output !== input) urlChanged = true;
      return output;
    };

    url = replaceParam(url, "timezone");
    url = replaceParam(url, "client-timezone");
    return { url, headers, headerChanged, urlChanged };
  }

  function extractIds(url) {
    const match = /\/connect-state\/v1\/player\/command\/from\/([^/?]+)\/to\/([^/?]+)/.exec(url);
    return match ? { from: match[1], to: match[2] } : { from: "?", to: "?" };
  }

  function decodeBody() {
    const raw = (typeof $request.bodyBytes !== "undefined" && $request.bodyBytes)
      ? $request.bodyBytes
      : $request.body;
    const bytes = toBytes(raw);
    if (!bytes || bytes.length === 0) return { text: "", rawBytes: 0, decodedBytes: 0, gzip: false, error: "no-body" };

    const gzipMagic = bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
    if (gzipMagic) {
      if (typeof $utils === "undefined" || typeof $utils.ungzip !== "function") {
        return { text: "", rawBytes: bytes.length, decodedBytes: 0, gzip: true, error: "ungzip-unavailable" };
      }
      try {
        const unzipped = $utils.ungzip(bytes);
        if (typeof unzipped === "string") {
          return { text: unzipped, rawBytes: bytes.length, decodedBytes: unzipped.length, gzip: true, error: "" };
        }
        const decoded = toBytes(unzipped);
        return {
          text: decodeUtf8(decoded),
          rawBytes: bytes.length,
          decodedBytes: decoded ? decoded.length : 0,
          gzip: true,
          error: decoded ? "" : "ungzip-empty"
        };
      } catch (e) {
        return { text: "", rawBytes: bytes.length, decodedBytes: 0, gzip: true, error: `ungzip:${e && e.message ? e.message : e}` };
      }
    }

    const text = typeof raw === "string" ? raw : decodeUtf8(bytes);
    return { text, rawBytes: bytes.length, decodedBytes: bytes.length, gzip: false, error: "" };
  }

  try {
    const originalUrl = $request.url;
    const ids = extractIds(originalUrl);
    const headers = $request.headers || {};
    const transferEncoding = getHeader(headers, "x-transfer-encoding").toLowerCase();
    const contentType = getHeader(headers, "content-type");
    const body = decodeBody();

    let endpoint = "unknown";
    let position = "n/a";
    let relative = "n/a";
    let context = "";
    let track = "";
    let reason = "";
    let license = "";
    let parseError = body.error;

    if (body.text) {
      try {
        const json = JSON.parse(body.text);
        const cmd = json && json.command ? json.command : {};
        endpoint = cmd.endpoint || "unknown";
        if (cmd.position != null) position = cmd.position;
        else if (cmd.value != null) position = cmd.value;
        relative = cmd.relative != null ? cmd.relative : "n/a";
        context = (cmd.context && (cmd.context.entity_uri || cmd.context.uri)) || "";
        track = (cmd.track && cmd.track.uri) ||
          (cmd.prepare_play_options && cmd.prepare_play_options.skip_to && cmd.prepare_play_options.skip_to.track_uri) || "";
        reason = (cmd.play_options && cmd.play_options.reason) || "";
        license = (cmd.prepare_play_options && cmd.prepare_play_options.license) ||
          (cmd.options && cmd.options.license) || "";
      } catch (e) {
        parseError = `json:${e && e.message ? e.message : e}`;
      }
    }

    console.log(
      `${TAG} endpoint=${endpoint}; position=${position}; relative=${relative}; ` +
      `from=${ids.from}; to=${ids.to}; context=${context || "n/a"}; track=${track || "n/a"}; ` +
      `reason=${reason || "n/a"}; license=${license || "n/a"}; ` +
      `xTransfer=${transferEncoding || "n/a"}; gzip=${body.gzip}; rawBytes=${body.rawBytes}; decodedBytes=${body.decodedBytes}; ` +
      `parseError=${parseError || "none"}`
    );

    const patched = applyTimezonePatch(originalUrl, headers);
    if (patched.headerChanged || patched.urlChanged) {
      console.log(`${TAG} timezone ${FROM_TZ} -> ${TO_TZ}; header=${patched.headerChanged}; url=${patched.urlChanged}`);
      $done({ url: patched.url, headers: patched.headers });
      return;
    }

    $done({});
  } catch (e) {
    console.log(`${TAG} fatal diagnostic error: ${e && e.message ? e.message : e}`);
    $done({});
  }
})();
