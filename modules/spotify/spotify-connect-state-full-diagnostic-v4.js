// LOCAL PATCH — Spotify Connect-State full playback diagnostic v4 (2026-09-27).
// Read-only protobuf diagnostic for PUT /connect-state/v1/devices/*.
// Captures queue, context index, options, origin, suppressions, signals,
// track/context metadata and command/state markers in one pass.
// It NEVER modifies the protobuf body. The only request mutation is the existing
// Europe/Moscow -> Europe/Helsinki timezone alignment used by the main module.

(() => {
  const TAG = "[Spotify Full Playback Diagnostic]";
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

  function parseStringMapEntry(bytes, start, end) {
    let key = "", value = "";
    const state = { pos: start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && field === 1) key = readString(bytes, state, end);
      else if (wire === 2 && field === 2) value = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return { key, value };
  }

  function parseRestrictions(bytes, start, end) {
    const out = {
      pause: [], resume: [], seek: [], peekPrev: [], peekNext: [],
      skipPrev: [], skipNext: [], toggleShuffle: [], setQueue: [],
      interrupt: [], transfer: [], remoteControl: [], play: [], stop: [],
      addQueue: [], viewQueue: []
    };
    const mapping = {
      1:"pause",2:"resume",3:"seek",4:"peekPrev",5:"peekNext",6:"skipPrev",7:"skipNext",
      10:"toggleShuffle",11:"setQueue",12:"interrupt",13:"transfer",14:"remoteControl",
      22:"play",23:"stop",24:"addQueue",36:"viewQueue"
    };
    const state = { pos: start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && mapping[field]) out[mapping[field]].push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseTrack(bytes, start, end) {
    const out = {
      uri:"", uid:"", provider:"", album:"", artist:"", removed:[], blocked:[],
      metadata:{}, restrictions:null, disallow:[]
    };
    const state = { pos: start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && field === 1) out.uri = readString(bytes, state, end);
      else if (wire === 2 && field === 2) out.uid = readString(bytes, state, end);
      else if (wire === 2 && field === 3) {
        const s = readSpan(bytes, state, end); const e = parseStringMapEntry(bytes, s.start, s.end);
        if (e.key) out.metadata[e.key] = e.value;
      }
      else if (wire === 2 && field === 4) out.removed.push(readString(bytes, state, end));
      else if (wire === 2 && field === 5) out.blocked.push(readString(bytes, state, end));
      else if (wire === 2 && field === 6) out.provider = readString(bytes, state, end);
      else if (wire === 2 && field === 7) { const s = readSpan(bytes, state, end); out.restrictions = parseRestrictions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 8) out.album = readString(bytes, state, end);
      else if (wire === 2 && field === 9) out.disallow.push(readString(bytes, state, end));
      else if (wire === 2 && field === 10) out.artist = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseContextIndex(bytes, start, end) {
    const out = { page:null, track:null };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 0 && field === 1) out.page = readVarint(bytes, state, end);
      else if (wire === 0 && field === 2) out.track = readVarint(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePlayOrigin(bytes, start, end) {
    const out = { feature:"", version:"", view:"", externalReferrer:"", referrer:"", device:"", featureClasses:[], restriction:"" };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && field === 1) out.feature = readString(bytes, state, end);
      else if (wire === 2 && field === 2) out.version = readString(bytes, state, end);
      else if (wire === 2 && field === 3) out.view = readString(bytes, state, end);
      else if (wire === 2 && field === 4) out.externalReferrer = readString(bytes, state, end);
      else if (wire === 2 && field === 5) out.referrer = readString(bytes, state, end);
      else if (wire === 2 && field === 6) { readString(bytes, state, end); out.device = "present"; }
      else if (wire === 2 && field === 7) out.featureClasses.push(readString(bytes, state, end));
      else if (wire === 2 && field === 8) out.restriction = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseOptions(bytes, start, end) {
    const out = { shuffle:null, repeatContext:null, repeatTrack:null, playbackSpeed:null, modes:{} };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 0 && field === 1) out.shuffle = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 2) out.repeatContext = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 3) out.repeatTrack = readVarint(bytes, state, end) !== 0;
      else if (wire === 5 && field === 4) { state.pos += 4; out.playbackSpeed = "present"; }
      else if (wire === 2 && field === 5) { const s = readSpan(bytes, state, end); const e = parseStringMapEntry(bytes, s.start, s.end); if (e.key) out.modes[e.key] = e.value; }
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseSuppressions(bytes, start, end) {
    const providers = [];
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && field === 1) providers.push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return providers;
  }

  function parsePlaybackQuality(bytes, start, end) {
    const out = { bitrate:null, strategy:null, targetBitrate:null, targetAvailable:null, hifi:null };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 0 && field === 1) out.bitrate = readVarint(bytes, state, end);
      else if (wire === 0 && field === 2) out.strategy = readVarint(bytes, state, end);
      else if (wire === 0 && field === 3) out.targetBitrate = readVarint(bytes, state, end);
      else if (wire === 0 && field === 4) out.targetAvailable = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 5) out.hifi = readVarint(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePlayerState(bytes, start, end) {
    const out = {
      timestamp:null, context:"", contextUrl:"", contextRestrictions:null, origin:null, index:null,
      track:null, playbackId:"", speed:null, posAsOf:null, duration:null,
      playing:null, paused:null, buffering:null, systemInitiated:null, options:null,
      restrictions:null, suppressions:[], prev:[], next:[], contextMetadata:{}, pageMetadata:{},
      sessionId:"", queueRevision:"", position:null, quality:null, signals:[], sessionCommandId:""
    };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 0 && field === 1) out.timestamp = readVarint(bytes, state, end);
      else if (wire === 2 && field === 2) out.context = readString(bytes, state, end);
      else if (wire === 2 && field === 3) out.contextUrl = readString(bytes, state, end);
      else if (wire === 2 && field === 4) { const s = readSpan(bytes, state, end); out.contextRestrictions = parseRestrictions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 5) { const s = readSpan(bytes, state, end); out.origin = parsePlayOrigin(bytes, s.start, s.end); }
      else if (wire === 2 && field === 6) { const s = readSpan(bytes, state, end); out.index = parseContextIndex(bytes, s.start, s.end); }
      else if (wire === 2 && field === 7) { const s = readSpan(bytes, state, end); out.track = parseTrack(bytes, s.start, s.end); }
      else if (wire === 2 && field === 8) out.playbackId = readString(bytes, state, end);
      else if (wire === 1 && field === 9) { state.pos += 8; out.speed = "present"; }
      else if (wire === 0 && field === 10) out.posAsOf = readVarint(bytes, state, end);
      else if (wire === 0 && field === 11) out.duration = readVarint(bytes, state, end);
      else if (wire === 0 && field === 12) out.playing = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 13) out.paused = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 14) out.buffering = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 15) out.systemInitiated = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 16) { const s = readSpan(bytes, state, end); out.options = parseOptions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 17) { const s = readSpan(bytes, state, end); out.restrictions = parseRestrictions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 18) { const s = readSpan(bytes, state, end); out.suppressions = parseSuppressions(bytes, s.start, s.end); }
      else if (wire === 2 && field === 19) { const s = readSpan(bytes, state, end); out.prev.push(parseTrack(bytes, s.start, s.end)); }
      else if (wire === 2 && field === 20) { const s = readSpan(bytes, state, end); out.next.push(parseTrack(bytes, s.start, s.end)); }
      else if (wire === 2 && field === 21) { const s = readSpan(bytes, state, end); const e = parseStringMapEntry(bytes, s.start, s.end); if (e.key) out.contextMetadata[e.key] = e.value; }
      else if (wire === 2 && field === 22) { const s = readSpan(bytes, state, end); const e = parseStringMapEntry(bytes, s.start, s.end); if (e.key) out.pageMetadata[e.key] = e.value; }
      else if (wire === 2 && field === 23) { readString(bytes, state, end); out.sessionId = "present"; }
      else if (wire === 2 && field === 24) out.queueRevision = readString(bytes, state, end);
      else if (wire === 0 && field === 25) out.position = readVarint(bytes, state, end);
      else if (wire === 2 && field === 32) { const s = readSpan(bytes, state, end); out.quality = parsePlaybackQuality(bytes, s.start, s.end); }
      else if (wire === 2 && field === 33) out.signals.push(readString(bytes, state, end));
      else if (wire === 2 && field === 35) out.sessionCommandId = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseCapabilities(bytes, start, end) {
    const out = { player:null, observable:null, playlistV2:null, controllable:null, commandRequest:null, fullState:null, gzip:null, setOptions:null, smartShuffle:null, remoteAudioQuality:null, connectCapabilities:"" };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      const boolFields = {2:"player",7:"observable",15:"playlistV2",16:"controllable",20:"commandRequest",22:"fullState",23:"gzip",25:"setOptions",33:"smartShuffle",37:"remoteAudioQuality"};
      if (wire === 0 && boolFields[field]) out[boolFields[field]] = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 27) out.connectCapabilities = readString(bytes, state, end);
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseDeviceInfo(bytes, start, end) {
    const out = { canPlay:null, capabilities:null, software:"", type:null, privateSession:null, productId:"", metadata:{}, offline:null, license:"", disallowPlayback:[], disallowTransfer:[] };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 0 && field === 1) out.canPlay = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 4) { const s = readSpan(bytes, state, end); out.capabilities = parseCapabilities(bytes, s.start, s.end); }
      else if (wire === 2 && field === 6) out.software = readString(bytes, state, end);
      else if (wire === 0 && field === 7) out.type = readVarint(bytes, state, end);
      else if (wire === 0 && field === 11) out.privateSession = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 16) { const s = readSpan(bytes, state, end); const e = parseStringMapEntry(bytes, s.start, s.end); if (e.key) out.metadata[e.key] = e.value; }
      else if (wire === 2 && field === 17) out.productId = readString(bytes, state, end);
      else if (wire === 0 && field === 21) out.offline = readVarint(bytes, state, end) !== 0;
      else if (wire === 2 && field === 23) out.license = readString(bytes, state, end);
      else if (wire === 2 && field === 27) out.disallowPlayback.push(readString(bytes, state, end));
      else if (wire === 2 && field === 28) out.disallowTransfer.push(readString(bytes, state, end));
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parseDevice(bytes, start, end) {
    const out = { info:null, player:null, platform:"" };
    const state = { pos:start };
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && field === 1) { const s = readSpan(bytes, state, end); out.info = parseDeviceInfo(bytes, s.start, s.end); }
      else if (wire === 2 && field === 2) { const s = readSpan(bytes, state, end); out.player = parsePlayerState(bytes, s.start, s.end); }
      else if (wire === 2 && field === 3) {
        const s = readSpan(bytes, state, end); const st = { pos:s.start };
        while (st.pos < s.end) {
          const t = readVarint(bytes, st, s.end), f = Math.floor(t/8), w = t&7;
          if (w === 2 && f === 1) out.platform = readString(bytes, st, s.end); else skipField(bytes, st, s.end, w);
        }
      }
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function parsePutState(bytes) {
    const out = { device:null, memberType:null, active:null, reason:null, messageId:null, hasLastCommandDevice:false, lastCommandMessageId:null, startedPlayingAt:null, playedForMs:null, clientTs:null, onlyPlayer:null };
    const state = { pos:0 }, end = bytes.length;
    while (state.pos < end) {
      const tag = readVarint(bytes, state, end), field = Math.floor(tag / 8), wire = tag & 7;
      if (wire === 2 && field === 2) { const s = readSpan(bytes, state, end); out.device = parseDevice(bytes, s.start, s.end); }
      else if (wire === 0 && field === 3) out.memberType = readVarint(bytes, state, end);
      else if (wire === 0 && field === 4) out.active = readVarint(bytes, state, end) !== 0;
      else if (wire === 0 && field === 5) out.reason = readVarint(bytes, state, end);
      else if (wire === 0 && field === 6) out.messageId = readVarint(bytes, state, end);
      else if (wire === 2 && field === 7) { readString(bytes, state, end); out.hasLastCommandDevice = true; }
      else if (wire === 0 && field === 8) out.lastCommandMessageId = readVarint(bytes, state, end);
      else if (wire === 0 && field === 9) out.startedPlayingAt = readVarint(bytes, state, end);
      else if (wire === 0 && field === 11) out.playedForMs = readVarint(bytes, state, end);
      else if (wire === 0 && field === 12) out.clientTs = readVarint(bytes, state, end);
      else if (wire === 0 && field === 13) out.onlyPlayer = readVarint(bytes, state, end) !== 0;
      else skipField(bytes, state, end, wire);
    }
    return out;
  }

  function reasonName(v) {
    const m = {0:"UNKNOWN",1:"SPIRC_HELLO",2:"SPIRC_NOTIFY",3:"NEW_DEVICE",4:"PLAYER_STATE_CHANGED",5:"VOLUME_CHANGED",6:"PICKER_OPENED",7:"BECAME_INACTIVE",8:"ALIAS_CHANGED",9:"NEW_CONNECTION",10:"PULL_PLAYBACK",11:"AUDIO_DRIVER_INFO_CHANGED",12:"PUT_STATE_RATE_LIMITED",13:"BACKEND_METADATA_APPLIED",14:"LOCAL_DEVICES_CHANGED",15:"GROUP_STATE_CHANGED",16:"PRIVATE_SESSION_CHANGED"};
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

  function compactTrack(t) {
    if (!t) return null;
    const md = t.metadata || {};
    const interesting = {};
    Object.keys(md).sort().slice(0, 20).forEach(k => { interesting[k] = md[k]; });
    return {
      uri:t.uri || "n/a", provider:t.provider || "n/a", uid:t.uid || "",
      disallow:t.disallow || [], removed:t.removed || [], blocked:t.blocked || [],
      seek:(t.restrictions && t.restrictions.seek) || [], metadata:interesting
    };
  }

  function compactMap(obj, max) {
    const out = {};
    Object.keys(obj || {}).sort().slice(0, max || 30).forEach(k => { out[k] = obj[k]; });
    return out;
  }

  try {
    const raw = (typeof $request.bodyBytes !== "undefined" && $request.bodyBytes) ? $request.bodyBytes : $request.body;
    let bytes = toBytes(raw);
    const rawBytes = bytes ? bytes.length : 0;
    let decompressed = false;
    if (bytes && bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b && typeof $utils !== "undefined" && typeof $utils.ungzip === "function") {
      try { bytes = toBytes($utils.ungzip(bytes)); decompressed = true; } catch (_) {}
    }

    if (bytes && bytes.length) {
      const ps = parsePutState(bytes);
      const dev = ps.device || {}, info = dev.info || {}, p = dev.player || {}, t = p.track || {}, o = p.origin || {}, idx = p.index || {}, opt = p.options || {}, caps = info.capabilities || {};
      const pr = p.restrictions || {}, cr = p.contextRestrictions || {};

      console.log(TAG + " state=" + JSON.stringify({
        reason:reasonName(ps.reason), active:ps.active, memberType:ps.memberType, messageId:ps.messageId,
        lastCommandPresent:ps.hasLastCommandDevice, lastCommandMessageId:ps.lastCommandMessageId,
        startedPlayingAt:ps.startedPlayingAt, playedForMs:ps.playedForMs, clientTs:ps.clientTs, onlyPlayer:ps.onlyPlayer,
        platform:dev.platform || "", license:info.license || "n/a", canPlay:info.canPlay,
        productId:info.productId || "", privateSession:info.privateSession, offline:info.offline,
        context:p.context || "n/a", contextUrl:p.contextUrl || "", indexPage:idx.page, indexTrack:idx.track,
        track:t.uri || "n/a", provider:t.provider || "n/a", posAsOf:p.posAsOf, position:p.position, duration:p.duration,
        playing:p.playing, paused:p.paused, buffering:p.buffering, systemInitiated:p.systemInitiated,
        queueRev:p.queueRevision || "", playbackIdPresent:!!p.playbackId, sessionIdPresent:!!p.sessionId,
        sessionCommandId:p.sessionCommandId || "", signals:p.signals || [], suppressions:p.suppressions || [],
        shuffle:opt.shuffle, repeatContext:opt.repeatContext, repeatTrack:opt.repeatTrack, modes:opt.modes || {},
        seekPlayer:pr.seek || [], seekContext:cr.seek || [], skipNextPlayer:pr.skipNext || [], skipNextContext:cr.skipNext || [],
        originFeature:o.feature || "", originView:o.view || "", originReferrer:o.referrer || "", originRestriction:o.restriction || "",
        originFeatureClasses:o.featureClasses || [], quality:p.quality || null,
        disallowPlayback:info.disallowPlayback || [], disallowTransfer:info.disallowTransfer || [],
        capabilities:caps
      }));

      console.log(TAG + " current=" + JSON.stringify(compactTrack(t)));
      console.log(TAG + " prev=" + JSON.stringify((p.prev || []).slice(0, 10).map(compactTrack)));
      console.log(TAG + " next=" + JSON.stringify((p.next || []).slice(0, 10).map(compactTrack)));
      console.log(TAG + " contextMetadata=" + JSON.stringify(compactMap(p.contextMetadata, 40)));
      console.log(TAG + " pageMetadata=" + JSON.stringify(compactMap(p.pageMetadata, 40)));
      console.log(TAG + " deviceMetadata=" + JSON.stringify(compactMap(info.metadata, 30)));
      console.log(TAG + " bytes raw=" + rawBytes + " decoded=" + bytes.length + " decompressed=" + decompressed);
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
