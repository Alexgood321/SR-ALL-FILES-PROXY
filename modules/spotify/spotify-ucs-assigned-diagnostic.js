// LOCAL PATCH — Spotify UCS assignedValues diagnostic (2026-09-27).
// Read-only diagnostic: decodes only enough protobuf structure to inspect
// UCS Configuration.assignedValues from bootstrap/customize responses.
// It NEVER modifies the response body and always finishes with $done({}).

(function () {
  const TAG = "[Spotify UCS Diagnostic]";

  function bodyBytes() {
    if (typeof $response === "undefined") return null;
    if ($response.bodyBytes) return new Uint8Array($response.bodyBytes);
    const b = $response.body;
    if (!b) return null;
    if (b instanceof Uint8Array) return b;
    if (b instanceof ArrayBuffer) return new Uint8Array(b);
    if (ArrayBuffer.isView && ArrayBuffer.isView(b)) {
      return new Uint8Array(b.buffer, b.byteOffset, b.byteLength);
    }
    return null;
  }

  function readVarint(bytes, pos, end) {
    let value = 0;
    let shift = 0;
    while (pos < end && shift <= 35) {
      const x = bytes[pos++];
      value += (x & 0x7f) * Math.pow(2, shift);
      if ((x & 0x80) === 0) return { value, pos };
      shift += 7;
    }
    throw new Error("invalid varint");
  }

  function readFields(bytes, start, end) {
    const out = [];
    let pos = start;
    while (pos < end) {
      const tag = readVarint(bytes, pos, end);
      pos = tag.pos;
      const num = Math.floor(tag.value / 8);
      const wire = tag.value & 7;
      if (!num) throw new Error("field 0");

      if (wire === 0) {
        const v = readVarint(bytes, pos, end);
        out.push({ num, wire, value: v.value });
        pos = v.pos;
      } else if (wire === 1) {
        if (pos + 8 > end) throw new Error("fixed64 overflow");
        out.push({ num, wire, start: pos, end: pos + 8 });
        pos += 8;
      } else if (wire === 2) {
        const len = readVarint(bytes, pos, end);
        pos = len.pos;
        const stop = pos + len.value;
        if (stop > end) throw new Error("length overflow");
        out.push({ num, wire, start: pos, end: stop });
        pos = stop;
      } else if (wire === 5) {
        if (pos + 4 > end) throw new Error("fixed32 overflow");
        out.push({ num, wire, start: pos, end: pos + 4 });
        pos += 4;
      } else {
        throw new Error("unsupported wire=" + wire);
      }
    }
    return out;
  }

  function children(bytes, range, num) {
    return readFields(bytes, range.start, range.end).filter(f => f.num === num && f.wire === 2);
  }

  function child(bytes, range, num) {
    const a = children(bytes, range, num);
    return a.length ? { start: a[0].start, end: a[0].end } : null;
  }

  function varintField(bytes, range, num) {
    const f = readFields(bytes, range.start, range.end).find(x => x.num === num && x.wire === 0);
    return f ? f.value : null;
  }

  function utf8(bytes, start, end) {
    if (typeof TextDecoder !== "undefined") {
      return new TextDecoder("utf-8").decode(bytes.slice(start, end));
    }
    let s = "";
    for (let i = start; i < end; i++) s += String.fromCharCode(bytes[i]);
    try { return decodeURIComponent(escape(s)); } catch (_) { return s; }
  }

  function stringField(bytes, range, num) {
    const f = readFields(bytes, range.start, range.end).find(x => x.num === num && x.wire === 2);
    return f ? utf8(bytes, f.start, f.end) : null;
  }

  function locateUcsSuccess(bytes, url) {
    const root = { start: 0, end: bytes.length };

    if (url.indexOf("/user-customization-service/v1/customize") !== -1) {
      // UcsResponseWrapper.success -> UcsResponse
      return child(bytes, root, 1);
    }

    if (url.indexOf("/bootstrap/v1/bootstrap") !== -1) {
      // BootstrapResponse.ucsResponseV0 (2)
      // -> UcsResponseWrapperV0.success (1)
      // -> UcsResponseWrapperSuccess.customization (1)
      // -> UcsResponseWrapper.success (1)
      const v0 = child(bytes, root, 2);
      if (!v0) return null;
      const v0Success = child(bytes, v0, 1);
      if (!v0Success) return null;
      const customization = child(bytes, v0Success, 1);
      if (!customization) return null;
      return child(bytes, customization, 1);
    }

    return null;
  }

  function assignedValues(bytes, ucs) {
    // UcsResponse.resolveSuccess(1) -> ResolveResponse.configuration(1)
    // -> Configuration.assignedValues repeated field 3.
    const resolve = child(bytes, ucs, 1);
    if (!resolve) return [];
    const config = child(bytes, resolve, 1);
    if (!config) return [];
    return children(bytes, config, 3).map(x => ({ start: x.start, end: x.end }));
  }

  function decodeAssigned(bytes, range) {
    const id = child(bytes, range, 1);
    const metadata = child(bytes, range, 2);
    const boolMsg = child(bytes, range, 3);
    const intMsg = child(bytes, range, 4);
    const enumMsg = child(bytes, range, 5);

    const scope = id ? (stringField(bytes, id, 1) || "") : "";
    const name = id ? (stringField(bytes, id, 2) || "") : "";
    const policyId = metadata ? varintField(bytes, metadata, 1) : null;

    let type = "unknown";
    let value = null;
    if (boolMsg) {
      type = "bool";
      value = !!varintField(bytes, boolMsg, 1);
    } else if (intMsg) {
      type = "int";
      value = varintField(bytes, intMsg, 1);
    } else if (enumMsg) {
      type = "enum";
      value = stringField(bytes, enumMsg, 1);
    }

    return { scope, name, type, value, policyId };
  }

  function interesting(v) {
    const s = (v.scope + "." + v.name).toLowerCase();
    return /mft|free[-_]?on[-_]?demand|capping|pick[-_]?and[-_]?shuffle|playback[-_]?timeout/.test(s);
  }

  try {
    const bytes = bodyBytes();
    const url = (typeof $request !== "undefined" && $request.url) ? $request.url : "";
    const source = url.indexOf("/bootstrap/") !== -1 ? "bootstrap" : "customize";

    if (!bytes || !bytes.length) {
      console.log(TAG + " source=" + source + " no-binary-body");
      return $done({});
    }

    const ucs = locateUcsSuccess(bytes, url);
    if (!ucs) {
      console.log(TAG + " source=" + source + " ucs-success-not-found bytes=" + bytes.length);
      return $done({});
    }

    const raw = assignedValues(bytes, ucs);
    const decoded = raw.map(r => decodeAssigned(bytes, r));
    const hits = decoded.filter(interesting);

    console.log(TAG + " source=" + source + " assigned=" + decoded.length + " matches=" + hits.length + " bytes=" + bytes.length);

    hits.forEach(v => {
      const policy = v.policyId === null ? "" : " policy=" + v.policyId;
      console.log(TAG + " " + v.scope + "." + v.name + " type=" + v.type + " value=" + String(v.value) + policy);
    });
  } catch (e) {
    console.log(TAG + " ERROR " + String(e && e.message ? e.message : e));
  }

  $done({});
})();
