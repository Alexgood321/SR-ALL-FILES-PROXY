// LOCAL PATCH — Spotify Connect-State queue diagnostic v3 (2026-09-27).
// Read-only protobuf diagnostic for PUT /connect-state/v1/devices/*.
// Adds prev/next queue tracks, suppressions and play-origin to the existing seek state view.
// The protobuf request body is NEVER modified. Only Europe/Moscow -> Europe/Helsinki
// is rewritten in explicit timezone header/query values, matching the main module behavior.

(() => {
  const TAG = "[Spotify Connect Queue Diagnostic]";
  const FROM_TZ = "Europe/Moscow";
  const TO_TZ = "Europe/Helsinki";

  function toBytes(body) {
    if (body == null) return null;
    if (typeof Uint8Array !== "undefined" && body instanceof Uint8Array) return body;
    if (typeof ArrayBuffer !== "undefined" && body instanceof ArrayBuffer) return new Uint8Array(body);
    if (body.buffer && typeof ArrayBuffer !== "undefined" && body.buffer instanceof ArrayBuffer) {
      return new Uint8Array(body.buffer, body.byteOffset || 0, body.byteLength != null ? body.byteLength : body.length);
    }
    if (typeof body === "string") {
      const out = new Uint8Array(body.length);
      for (let i = 0; i < body.length; i++) out[i] = body.charCodeAt(i) & 0xff;
      return out;
    }
    return null;
  }

  function readVarint(bytes, state, end) {
    let value = 0, factor = 1;
    for (let i = 0; i < 10; i++) {
      if (state.pos >= end) throw new Error("unexpected EOF in varint");
      const b = bytes[state.pos++];
      value += (b & 0x7f) * factor;
      if ((b & 0x80) === 0) return value;
      factor *= 128;
    }
    throw new Error("invalid varint");
  }

  function readSpan(bytes, state, end) {
    const len = readVarint(bytes, state, end);
    const start = state.pos, stop = start + len;
    if (stop > end) throw new Error("field exceeds message");
    state.pos = stop;
    return { start, end: stop };
  }

  function skipField(bytes, state, end, wire) {
    if (wire === 0) readVarint(bytes, state, end);
    else if (wire === 1) state.pos += 8;
    else if (wire === 2) readSpan(bytes, state, end);
    else if (wire === 5) state.pos += 4;
    else throw new Error("unsupported wire=" + wire);
    if (state.pos > end) throw new Error("skip exceeded message");
  }

  function decodeUtf8(bytes, start, end) {
    if (typeof TextDecoder !== "undefined") {
      try { return new TextDecoder("utf-8").decode(bytes.slice(start, end)); } catch (_) {}
    }
    let out = "";
    for (let i = start; i < end; i++) out += String.fromCharCode(bytes[i]);
    try { return decodeURIComponent(escape(out)); } catch (_) { return out; }
  }

  function readString(bytes, state, end) {
    const span = readSpan(bytes, state, end);
    return decodeUtf8(bytes, span.start, span.end);
  }

  function parseRestrictions(bytes, start, end) {
    const out = { seek: [], skipPrev: [], skipNext: [] };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && (field === 3 || field === 6 || field === 7)) {
        const v = readString(bytes, state, end);
        if (field === 3) out.seek.push(v);
        else if (field === 6) out.skipPrev.push(v);
        else out.skipNext.push(v);
      } else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseTrack(bytes, start, end) {
    const out = { uri: "", provider: "", restrictions: { seek: [], skipPrev: [], skipNext: [] }, disallow: [] };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && field === 1) out.uri = readString(bytes, state, end);
      else if (wire === 2 && field === 6) out.provider = readString(bytes, state, end);
      else if (wire === 2 && field === 7) {
        const span = readSpan(bytes, state, end);
        out.restrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 2 && field === 9) out.disallow.push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePlayOrigin(bytes, start, end) {
    const out = { feature: "", view: "", referrer: "", restriction: "" };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && field === 1) out.feature = readString(bytes, state, end);
      else if (wire === 2 && field === 3) out.view = readString(bytes, state, end);
      else if (wire === 2 && field === 5) out.referrer = readString(bytes, state, end);
      else if (wire === 2 && field === 8) out.restriction = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseSuppressions(bytes, start, end) {
    const providers = [];
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && field === 1) providers.push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return providers;
  }

  function parsePlayerState(bytes, start, end) {
    const out = {
      context: "", track: null, posAsOf: null, duration: null, position: null,
      restrictions: { seek: [], skipPrev: [], skipNext: [] }, contextRestrictions: { seek: [], skipPrev: [], skipNext: [] },
      prev: [], next: [], suppressions: [], origin: null, queueRevision: ""
    };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && field === 2) out.context = readString(bytes, state, end);
      else if (wire === 2 && field === 4) { const s = readSpan(bytes, state, end); out.contextRestrictions = parseRestrictions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 5) { const s = readSpan(bytes, state, end); out.origin = parsePlayOrigin(bytes, s.start, s.end); }
      else if (wire === 2 && field === 7) { const s = readSpan(bytes, state, end); out.track = parseTrack(bytes, s.start, s.end); }
      else if (wire === 0 && field === 10) out.posAsOf = readVarint(bytes, state, end);
      else if (wire === 0 && field === 11) out.duration = readVarint(bytes, state, end);
      else if (wire === 2 && field === 17) { const s = readSpan(bytes, state, end); out.restrictions = parseRestrictions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 18) { const s = readSpan(bytes, state, end); out.suppressions = parseSuppressions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 19) { const s = readSpan(bytes, state, end); out.prev.push(parseTrack(bytes, s.start, s.end)); }
      else if (wire === 2 && field === 20) { const s = readSpan(bytes, state, end); out.next.push(parseTrack(bytes, s.start, s.end)); }
      else if (wire === 2 && field === 24) out.queueRevision = readString(bytes, state, end);
      else if (wire === 0 && field === 25) out.position = readVarint(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseDeviceInfo(bytes, start, end) {
    const out = { canPlay: null, license: "" };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 0 && field === 1) out.canPlay = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 23) out.license = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseDevice(bytes, start, end) {
    const out = { info: null, player: null };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && field === 1) { const s = readSpan(bytes, state, end); out.info = parseDeviceInfo(bytes, s.start, s.end); }
      else if (wire === 2 && field === 2) { const s = readSpan(bytes, state, end); out.player = parsePlayerState(bytes, s.start, s.end); }
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePutState(bytes) {
    const out = { device: null, reason: null, active: null };
    const state = { pos: 0 }, end = bytes.length;
    while (state.pos < end) {
      const key = readVarint(bytes, state, end), field = Math.floor(key / 8), wire = key & 7;
      if (wire === 2 && field === 2) { const s = readSpan(bytes, state, end); out.device = parseDevice(bytes, s.start, s.end); }
      else if (wire === 0 && field === 4) out.active = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 5) out.reason = readVarint(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function reasonName(v) {
    const m = {4:"PLAYER_STATE_CHANGED",9:"NEW_CONNECTION",11:"AUDIO_DRIVER_INFO_CHANGED",13:"BACKEND_METADATA_APPLIED"};
    return Object.prototype.hasOwnProperty.call(m, v) ? m[v] : String(v == null ? "n/a" : v);
  }

  function applyTimezone(url, originalHeaders) {
    const headers = Object.assign({}, originalHeaders || {});
    let h = false, u = false;
    Object.keys(headers).forEach(k => {
      if (/^(time-zone|x-client-timezone)$/i.test(k) && String(headers[k]).toLowerCase() === FROM_TZ.toLowerCase()) {
        headers[k] = TO_TZ; h = true;
      }
    });
    const before = url;
    url = url
      .replace(/([?&]timezone=)Europe(?:%2F|\/)Moscow(?=(&|$))/ig, "$1Europe%2FHelsinki")
      .replace(/([?&]client-timezone=)Europe(?:%2F|\/)Moscow(?=(&|$))/ig, "$1Europe%2FHelsinki");
    u = url !== before;
    return { url, headers, h, u };
  }

  function compactTracks(list) {
    return (list || []).slice(0, 10).map(t => (t.uri || "n/a") + "@" + (t.provider || "n/a"));
  }

  try {
    const raw = (typeof $request.bodyBytes !== "undefined" && $request.bodyBytes) ? $request.bodyBytes : $request.body;
    let bytes = toBytes(raw);
    if (bytes && bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b && typeof $utils !== "undefined" && typeof $utils.ungzip === "function") {
      try { bytes = toBytes($utils.ungzip(bytes)); } catch (_) {}
    }

    if (bytes && bytes.length) {
      const ps = parsePutState(bytes);
      const dev = ps.device || {}, info = dev.info || {}, p = dev.player || {}, t = p.track || {}, o = p.origin || {};
      console.log(TAG +
        " reason=" + reasonName(ps.reason) +
        " active=" + ps.active +
        " license=" + (info.license || "n/a") +
        " context=" + (p.context || "n/a") +
        " track=" + (t.uri || "n/a") +
        " provider=" + (t.provider || "n/a") +
        " posAsOf=" + (p.posAsOf == null ? "n/a" : p.posAsOf) +
        " position=" + (p.position == null ? "n/a" : p.position) +
        " duration=" + (p.duration == null ? "n/a" : p.duration) +
        " seek=" + JSON.stringify((p.restrictions && p.restrictions.seek) || []) +
        " suppressions=" + JSON.stringify(p.suppressions || []) +
        " originFeature=" + (o.feature || "n/a") +
        " originRestriction=" + (o.restriction || "n/a") +
        " queueRev=" + (p.queueRevision || "n/a"));
      console.log(TAG + " prev=" + JSON.stringify(compactTracks(p.prev)));
      console.log(TAG + " next=" + JSON.stringify(compactTracks(p.next)));
    } else {
      console.log(TAG + " no-body");
    }

    const patched = applyTimezone($request.url, $request.headers || {});
    const out = {};
    if (patched.u) out.url = patched.url;
    if (patched.h) out.headers = patched.headers;
    $done(out);
  } catch (e) {
    console.log(TAG + " ERROR " + String(e && e.message ? e.message : e));
    $done({});
  }
})();
