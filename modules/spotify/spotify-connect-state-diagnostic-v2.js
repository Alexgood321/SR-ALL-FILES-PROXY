// LOCAL PATCH — Spotify Connect-State seek diagnostic v2.
// Purpose: inspect PUT /connect-state/v1/devices/* around seek -> next-track,
// while also applying the existing Europe/Moscow -> Europe/Helsinki timezone
// patch because this specific rule runs before the generic timezone rule.
//
// Diagnostic fields:
//   PutStateRequest.reason / is_active / message_id
//   DeviceInfo.license / can_play / disallow_playback_reasons
//   PlayerState.context_uri / current track / position / duration
//   context, player and track disallow_seeking_reasons
//   context/player skip prev/next reasons and track disallow_reasons
//
// Safety:
//   - never changes protobuf body
//   - only changes explicit timezone header/query values Moscow -> Helsinki
//   - gzip is read only for diagnostics
//   - parse failures are passthrough

(() => {
  const TAG = "[Spotify Connect State Diagnostic]";
  const FROM_TZ = "Europe/Moscow";
  const TO_TZ = "Europe/Helsinki";

  function getHeader(headers, wanted) {
    const lower = wanted.toLowerCase();
    for (const key of Object.keys(headers || {})) {
      if (key.toLowerCase() === lower) return String(headers[key]);
    }
    return "";
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

  function readVarint(bytes, state, end) {
    let value = 0;
    let factor = 1;
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
    const length = readVarint(bytes, state, end);
    const start = state.pos;
    const finish = start + length;
    if (finish > end) throw new Error("field exceeds message");
    state.pos = finish;
    return { start, end: finish };
  }

  function skipField(bytes, state, end, wire) {
    if (wire === 0) readVarint(bytes, state, end);
    else if (wire === 1) state.pos += 8;
    else if (wire === 2) {
      const span = readSpan(bytes, state, end);
      state.pos = span.end;
    } else if (wire === 5) state.pos += 4;
    else throw new Error(`unsupported wire ${wire}`);
    if (state.pos > end) throw new Error("skip exceeded message");
  }

  function decodeUtf8(bytes, start, end) {
    let out = "";
    for (let i = start; i < end;) {
      const b1 = bytes[i++];
      if (b1 < 0x80) out += String.fromCharCode(b1);
      else if ((b1 & 0xe0) === 0xc0 && i < end) {
        const b2 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x1f) << 6) | (b2 & 0x3f));
      } else if ((b1 & 0xf0) === 0xe0 && i + 1 < end) {
        const b2 = bytes[i++], b3 = bytes[i++];
        out += String.fromCharCode(((b1 & 0x0f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f));
      } else if ((b1 & 0xf8) === 0xf0 && i + 2 < end) {
        const b2 = bytes[i++], b3 = bytes[i++], b4 = bytes[i++];
        let cp = ((b1 & 7) << 18) | ((b2 & 63) << 12) | ((b3 & 63) << 6) | (b4 & 63);
        cp -= 0x10000;
        out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
      } else out += "�";
    }
    return out;
  }

  function readString(bytes, state, end) {
    const span = readSpan(bytes, state, end);
    return decodeUtf8(bytes, span.start, span.end);
  }

  function emptyRestrictions() {
    return { seek: [], skipPrev: [], skipNext: [], play: [] };
  }

  function parseRestrictions(bytes, start, end) {
    const out = emptyRestrictions();
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;
      if (wire === 2 && (field === 3 || field === 6 || field === 7 || field === 22)) {
        const value = readString(bytes, state, end);
        if (field === 3) out.seek.push(value);
        else if (field === 6) out.skipPrev.push(value);
        else if (field === 7) out.skipNext.push(value);
        else out.play.push(value);
      } else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseTrack(bytes, start, end) {
    const out = { uri: "", provider: "", restrictions: emptyRestrictions(), disallowReasons: [] };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;
      if (wire === 2 && field === 1) out.uri = readString(bytes, state, end);
      else if (wire === 2 && field === 6) out.provider = readString(bytes, state, end);
      else if (wire === 2 && field === 7) {
        const span = readSpan(bytes, state, end);
        out.restrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 2 && field === 9) out.disallowReasons.push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePlayerState(bytes, start, end) {
    const out = {
      context: "",
      positionAsOf: null,
      duration: null,
      position: null,
      isPlaying: null,
      isPaused: null,
      isBuffering: null,
      contextRestrictions: emptyRestrictions(),
      restrictions: emptyRestrictions(),
      track: null
    };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;
      if (wire === 2 && field === 2) out.context = readString(bytes, state, end);
      else if (wire === 2 && field === 4) {
        const span = readSpan(bytes, state, end);
        out.contextRestrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 2 && field === 7) {
        const span = readSpan(bytes, state, end);
        out.track = parseTrack(bytes, span.start, span.end);
      } else if (wire === 0 && field === 10) out.positionAsOf = readVarint(bytes, state, end);
      else if (wire === 0 && field === 11) out.duration = readVarint(bytes, state, end);
      else if (wire === 0 && field === 12) out.isPlaying = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 13) out.isPaused = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 14) out.isBuffering = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 17) {
        const span = readSpan(bytes, state, end);
        out.restrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 0 && field === 25) out.position = readVarint(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseDeviceInfo(bytes, start, end) {
    const out = { canPlay: null, license: "", disallowPlayback: [] };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;
      if (wire === 0 && field === 1) out.canPlay = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 23) out.license = readString(bytes, state, end);
      else if (wire === 2 && field === 27) out.disallowPlayback.push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseDevice(bytes, start, end) {
    const out = { info: null, player: null };
    const state = { pos: start };
    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;
      if (wire === 2 && field === 1) {
        const span = readSpan(bytes, state, end);
        out.info = parseDeviceInfo(bytes, span.start, span.end);
      } else if (wire === 2 && field === 2) {
        const span = readSpan(bytes, state, end);
        out.player = parsePlayerState(bytes, span.start, span.end);
      } else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePutState(bytes) {
    const out = { device: null, isActive: null, reason: null, messageId: null, onlyWritePlayerState: null };
    const state = { pos: 0 };
    const end = bytes.length;
    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;
      if (wire === 2 && field === 2) {
        const span = readSpan(bytes, state, end);
        out.device = parseDevice(bytes, span.start, span.end);
      } else if (wire === 0 && field === 4) out.isActive = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 5) out.reason = readVarint(bytes, state, end);
      else if (wire === 0 && field === 6) out.messageId = readVarint(bytes, state, end);
      else if (wire === 0 && field === 13) out.onlyWritePlayerState = readVarint(bytes, state, end) !== 0;
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function reasonName(v) {
    const names = {
      0: "UNKNOWN", 1: "SPIRC_HELLO", 2: "SPIRC_NOTIFY", 3: "NEW_DEVICE",
      4: "PLAYER_STATE_CHANGED", 5: "VOLUME_CHANGED", 6: "PICKER_OPENED",
      7: "BECAME_INACTIVE", 8: "ALIAS_CHANGED", 9: "NEW_CONNECTION",
      10: "PULL_PLAYBACK", 11: "AUDIO_DRIVER_INFO_CHANGED", 12: "PUT_STATE_RATE_LIMITED",
      13: "BACKEND_METADATA_APPLIED", 14: "LOCAL_DEVICES_CHANGED",
      15: "GROUP_STATE_CHANGED", 16: "PRIVATE_SESSION_CHANGED"
    };
    return Object.prototype.hasOwnProperty.call(names, v) ? names[v] : `UNKNOWN_${v}`;
  }

  function arr(v) { return JSON.stringify(v || []); }

  try {
    const originalUrl = $request.url;
    const headers = $request.headers || {};
    const raw = (typeof $request.bodyBytes !== "undefined" && $request.bodyBytes) ? $request.bodyBytes : $request.body;
    let bytes = toBytes(raw);
    const transfer = getHeader(headers, "x-transfer-encoding").toLowerCase();
    const rawBytes = bytes ? bytes.length : 0;
    const gzipMagic = !!(bytes && bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b);
    let decompressed = false;
    let parseError = "";

    if (gzipMagic) {
      if (typeof $utils === "undefined" || typeof $utils.ungzip !== "function") {
        parseError = "gzip body but $utils.ungzip unavailable";
      } else {
        try {
          bytes = toBytes($utils.ungzip(bytes));
          decompressed = true;
          if (!bytes || !bytes.length) parseError = "ungzip returned empty body";
        } catch (e) {
          parseError = `ungzip:${e && e.message ? e.message : e}`;
        }
      }
    }

    if (!parseError && bytes && bytes.length) {
      try {
        const state = parsePutState(bytes);
        const device = state.device || {};
        const info = device.info || {};
        const player = device.player || {};
        const track = player.track || {};
        const cr = player.contextRestrictions || emptyRestrictions();
        const pr = player.restrictions || emptyRestrictions();
        const tr = track.restrictions || emptyRestrictions();

        console.log(
          `${TAG} reason=${reasonName(state.reason)}(${state.reason == null ? "n/a" : state.reason}); ` +
          `messageId=${state.messageId == null ? "n/a" : state.messageId}; active=${state.isActive}; ` +
          `onlyPlayer=${state.onlyWritePlayerState}; license=${info.license || "n/a"}; canPlay=${info.canPlay}; ` +
          `context=${player.context || "n/a"}; track=${track.uri || "n/a"}; provider=${track.provider || "n/a"}; ` +
          `posAsOf=${player.positionAsOf == null ? "n/a" : player.positionAsOf}; ` +
          `position=${player.position == null ? "n/a" : player.position}; duration=${player.duration == null ? "n/a" : player.duration}; ` +
          `playing=${player.isPlaying}; paused=${player.isPaused}; buffering=${player.isBuffering}; ` +
          `xTransfer=${transfer || "n/a"}; gzipMagic=${gzipMagic}; decompressed=${decompressed}; rawBytes=${rawBytes}; decodedBytes=${bytes.length}`
        );
        console.log(
          `${TAG} seek context=${arr(cr.seek)}; player=${arr(pr.seek)}; track=${arr(tr.seek)}; ` +
          `trackDisallow=${arr(track.disallowReasons)}; deviceDisallowPlayback=${arr(info.disallowPlayback)}`
        );
        console.log(
          `${TAG} skip contextPrev=${arr(cr.skipPrev)}; contextNext=${arr(cr.skipNext)}; ` +
          `playerPrev=${arr(pr.skipPrev)}; playerNext=${arr(pr.skipNext)}; ` +
          `trackPrev=${arr(tr.skipPrev)}; trackNext=${arr(tr.skipNext)}`
        );
      } catch (e) {
        parseError = `protobuf:${e && e.message ? e.message : e}`;
      }
    } else if (!bytes || !bytes.length) {
      parseError = parseError || "no-body";
    }

    if (parseError) {
      console.log(`${TAG} parseError=${parseError}; xTransfer=${transfer || "n/a"}; gzipMagic=${gzipMagic}; rawBytes=${rawBytes}`);
    }

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
