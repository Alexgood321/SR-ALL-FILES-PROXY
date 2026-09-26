// LOCAL PATCH — Spotify Connect-State seek diagnostic.
// Purpose: inspect Spotify's PUT /connect-state/v1/devices/* protobuf state
// around the seek -> next-track bug without changing the request.
//
// Known protobuf path:
//   PutStateRequest.device (field 2)
//     -> Device.player_state (field 2)
//       -> PlayerState.context_restrictions (field 4)
//       -> PlayerState.track (field 7)
//       -> PlayerState.restrictions (field 17)
//
// Restrictions.disallow_seeking_reasons is field 3.
// The request may be gzip-compressed via X-Transfer-Encoding: gzip.
//
// LOCAL PATCH SAFETY / SCOPE:
//   - diagnostic only; never returns a replacement body or headers
//   - reads only Spotify connect-state PUT request bodies
//   - if gzip decoding or protobuf parsing fails, request is passed through
//   - does not modify player state, account attributes, queue, track or position

(() => {
  const TAG = "[Spotify Connect Diagnostic]";

  function getHeader(headers, wanted) {
    const lower = wanted.toLowerCase();
    for (const key of Object.keys(headers || {})) {
      if (key.toLowerCase() === lower) return String(headers[key]);
    }
    return "";
  }

  function toBytes(body) {
    if (body == null) return null;

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

    // Some script engines expose binary data as a byte-string.
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
      if (state.pos >= end) throw new Error("unexpected EOF while reading varint");
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
    if (finish > end) throw new Error("length-delimited field exceeds message");
    state.pos = finish;
    return { start, end: finish, length };
  }

  function skipField(bytes, state, end, wireType) {
    switch (wireType) {
      case 0:
        readVarint(bytes, state, end);
        return;
      case 1:
        state.pos += 8;
        break;
      case 2: {
        const span = readSpan(bytes, state, end);
        state.pos = span.end;
        break;
      }
      case 5:
        state.pos += 4;
        break;
      default:
        throw new Error(`unsupported wire type ${wireType}`);
    }

    if (state.pos > end) throw new Error("field exceeds message");
  }

  function decodeUtf8(bytes, start, end) {
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

  function readString(bytes, state, end) {
    const span = readSpan(bytes, state, end);
    return decodeUtf8(bytes, span.start, span.end);
  }

  function parseRestrictions(bytes, start, end) {
    const result = {
      seek: [],
      skipPrev: [],
      skipNext: [],
      play: []
    };
    const state = { pos: start };

    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;

      if (wire === 2 && (field === 3 || field === 6 || field === 7 || field === 22)) {
        const value = readString(bytes, state, end);
        if (field === 3) result.seek.push(value);
        else if (field === 6) result.skipPrev.push(value);
        else if (field === 7) result.skipNext.push(value);
        else result.play.push(value);
        continue;
      }

      skipField(bytes, state, end, wire);
    }

    return result;
  }

  function parseProvidedTrack(bytes, start, end) {
    const result = {
      uri: "",
      provider: "",
      albumUri: "",
      artistUri: "",
      removed: [],
      blocked: [],
      disallowReasons: [],
      restrictions: { seek: [], skipPrev: [], skipNext: [], play: [] }
    };
    const state = { pos: start };

    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;

      if (wire === 2 && field === 1) {
        result.uri = readString(bytes, state, end);
      } else if (wire === 2 && field === 4) {
        result.removed.push(readString(bytes, state, end));
      } else if (wire === 2 && field === 5) {
        result.blocked.push(readString(bytes, state, end));
      } else if (wire === 2 && field === 6) {
        result.provider = readString(bytes, state, end);
      } else if (wire === 2 && field === 7) {
        const span = readSpan(bytes, state, end);
        result.restrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 2 && field === 8) {
        result.albumUri = readString(bytes, state, end);
      } else if (wire === 2 && field === 9) {
        result.disallowReasons.push(readString(bytes, state, end));
      } else if (wire === 2 && field === 10) {
        result.artistUri = readString(bytes, state, end);
      } else {
        skipField(bytes, state, end, wire);
      }
    }

    return result;
  }

  function parsePlayerState(bytes, start, end) {
    const result = {
      contextUri: "",
      positionAsOfTimestamp: null,
      duration: null,
      position: null,
      isPlaying: null,
      isPaused: null,
      isBuffering: null,
      contextRestrictions: { seek: [], skipPrev: [], skipNext: [], play: [] },
      restrictions: { seek: [], skipPrev: [], skipNext: [], play: [] },
      track: null
    };
    const state = { pos: start };

    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;

      if (wire === 2 && field === 2) {
        result.contextUri = readString(bytes, state, end);
      } else if (wire === 2 && field === 4) {
        const span = readSpan(bytes, state, end);
        result.contextRestrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 2 && field === 7) {
        const span = readSpan(bytes, state, end);
        result.track = parseProvidedTrack(bytes, span.start, span.end);
      } else if (wire === 0 && field === 10) {
        result.positionAsOfTimestamp = readVarint(bytes, state, end);
      } else if (wire === 0 && field === 11) {
        result.duration = readVarint(bytes, state, end);
      } else if (wire === 0 && field === 12) {
        result.isPlaying = readVarint(bytes, state, end) !== 0;
      } else if (wire === 0 && field === 13) {
        result.isPaused = readVarint(bytes, state, end) !== 0;
      } else if (wire === 0 && field === 14) {
        result.isBuffering = readVarint(bytes, state, end) !== 0;
      } else if (wire === 2 && field === 17) {
        const span = readSpan(bytes, state, end);
        result.restrictions = parseRestrictions(bytes, span.start, span.end);
      } else if (wire === 0 && field === 25) {
        result.position = readVarint(bytes, state, end);
      } else {
        skipField(bytes, state, end, wire);
      }
    }

    return result;
  }

  function parseDeviceInfo(bytes, start, end) {
    const result = { canPlay: null, license: "", disallowPlaybackReasons: [] };
    const state = { pos: start };

    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;

      if (wire === 0 && field === 1) {
        result.canPlay = readVarint(bytes, state, end) !== 0;
      } else if (wire === 2 && field === 23) {
        result.license = readString(bytes, state, end);
      } else if (wire === 2 && field === 27) {
        result.disallowPlaybackReasons.push(readString(bytes, state, end));
      } else {
        skipField(bytes, state, end, wire);
      }
    }

    return result;
  }

  function parseDevice(bytes, start, end) {
    const result = { deviceInfo: null, playerState: null };
    const state = { pos: start };

    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;

      if (wire === 2 && field === 1) {
        const span = readSpan(bytes, state, end);
        result.deviceInfo = parseDeviceInfo(bytes, span.start, span.end);
      } else if (wire === 2 && field === 2) {
        const span = readSpan(bytes, state, end);
        result.playerState = parsePlayerState(bytes, span.start, span.end);
      } else {
        skipField(bytes, state, end, wire);
      }
    }

    return result;
  }

  function parsePutState(bytes) {
    const result = {
      device: null,
      isActive: null,
      reason: null,
      messageId: null,
      onlyWritePlayerState: null
    };
    const state = { pos: 0 };
    const end = bytes.length;

    while (state.pos < end) {
      const key = readVarint(bytes, state, end);
      const field = Math.floor(key / 8);
      const wire = key & 7;

      if (wire === 2 && field === 2) {
        const span = readSpan(bytes, state, end);
        result.device = parseDevice(bytes, span.start, span.end);
      } else if (wire === 0 && field === 4) {
        result.isActive = readVarint(bytes, state, end) !== 0;
      } else if (wire === 0 && field === 5) {
        result.reason = readVarint(bytes, state, end);
      } else if (wire === 0 && field === 6) {
        result.messageId = readVarint(bytes, state, end);
      } else if (wire === 0 && field === 13) {
        result.onlyWritePlayerState = readVarint(bytes, state, end) !== 0;
      } else {
        skipField(bytes, state, end, wire);
      }
    }

    return result;
  }

  function reasonName(value) {
    const names = {
      0: "UNKNOWN",
      1: "SPIRC_HELLO",
      2: "SPIRC_NOTIFY",
      3: "NEW_DEVICE",
      4: "PLAYER_STATE_CHANGED",
      5: "VOLUME_CHANGED",
      6: "PICKER_OPENED",
      7: "BECAME_INACTIVE",
      8: "ALIAS_CHANGED",
      9: "NEW_CONNECTION",
      10: "PULL_PLAYBACK",
      11: "AUDIO_DRIVER_INFO_CHANGED",
      12: "PUT_STATE_RATE_LIMITED",
      13: "BACKEND_METADATA_APPLIED",
      14: "LOCAL_DEVICES_CHANGED",
      15: "GROUP_STATE_CHANGED",
      16: "PRIVATE_SESSION_CHANGED"
    };
    return Object.prototype.hasOwnProperty.call(names, value) ? names[value] : `UNKNOWN_${value}`;
  }

  function fmt(value) {
    return value == null ? "n/a" : String(value);
  }

  function arr(value) {
    return JSON.stringify(value || []);
  }

  try {
    const headers = $request.headers || {};
    const transferEncoding = getHeader(headers, "x-transfer-encoding").toLowerCase();
    const rawBody = (typeof $request.bodyBytes !== "undefined" && $request.bodyBytes)
      ? $request.bodyBytes
      : $request.body;
    let bytes = toBytes(rawBody);

    if (!bytes || bytes.length === 0) {
      console.log(`${TAG} no binary request body; passthrough`);
      $done({});
      return;
    }

    const gzipMagic = bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
    let decompressed = false;

    if (gzipMagic) {
      if (typeof $utils === "undefined" || typeof $utils.ungzip !== "function") {
        console.log(`${TAG} gzip body detected but $utils.ungzip is unavailable; passthrough`);
        $done({});
        return;
      }

      bytes = toBytes($utils.ungzip(bytes));
      if (!bytes || bytes.length === 0) throw new Error("ungzip returned empty body");
      decompressed = true;
    }

    const parsed = parsePutState(bytes);
    const device = parsed.device || {};
    const deviceInfo = device.deviceInfo || {};
    const player = device.playerState;

    if (!player) {
      console.log(
        `${TAG} parsed PutState without PlayerState; bytes=${bytes.length}; ` +
        `gzipHeader=${transferEncoding.includes("gzip")}; gunzipped=${decompressed}; ` +
        `reason=${fmt(parsed.reason)}; msg=${fmt(parsed.messageId)}`
      );
      $done({});
      return;
    }

    const track = player.track || {};
    const contextR = player.contextRestrictions || {};
    const playerR = player.restrictions || {};
    const trackR = track.restrictions || {};

    console.log(
      `${TAG} reason=${reasonName(parsed.reason)}(${fmt(parsed.reason)}); active=${fmt(parsed.isActive)}; ` +
      `msg=${fmt(parsed.messageId)}; onlyPlayer=${fmt(parsed.onlyWritePlayerState)}; ` +
      `gzipHeader=${transferEncoding.includes("gzip")}; gunzipped=${decompressed}; ` +
      `deviceLicense=${deviceInfo.license || "n/a"}; canPlay=${fmt(deviceInfo.canPlay)}; ` +
      `context=${player.contextUri || "n/a"}; track=${track.uri || "n/a"}; ` +
      `posAsOf=${fmt(player.positionAsOfTimestamp)}; position=${fmt(player.position)}; duration=${fmt(player.duration)}; ` +
      `playing=${fmt(player.isPlaying)}; paused=${fmt(player.isPaused)}; buffering=${fmt(player.isBuffering)}`
    );

    console.log(
      `${TAG} seek context=${arr(contextR.seek)}; player=${arr(playerR.seek)}; ` +
      `track=${arr(trackR.seek)}; trackDisallow=${arr(track.disallowReasons)}`
    );

    console.log(
      `${TAG} skip contextPrev=${arr(contextR.skipPrev)}; contextNext=${arr(contextR.skipNext)}; ` +
      `playerPrev=${arr(playerR.skipPrev)}; playerNext=${arr(playerR.skipNext)}; ` +
      `trackPrev=${arr(trackR.skipPrev)}; trackNext=${arr(trackR.skipNext)}; ` +
      `removed=${arr(track.removed)}; blocked=${arr(track.blocked)}; ` +
      `deviceDisallowPlayback=${arr(deviceInfo.disallowPlaybackReasons)}`
    );
  } catch (error) {
    console.log(`${TAG} parse error: ${error && error.message ? error.message : error}; passthrough`);
  }

  // LOCAL PATCH: diagnostic only. Never replace the request body.
  $done({});
})();
