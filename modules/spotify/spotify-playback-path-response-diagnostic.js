// LOCAL PATCH — Spotify playback-path response diagnostic (2026-09-27).
// Pure read-only diagnostic. It never rewrites Spotify responses.
// It extracts visible Spotify URIs from the response body so we can correlate
// free-tier/scrollsita/on-demand responses with the actual track transitions.

(function () {
  const TAG = "[Spotify Playback Path]";

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

  function bodyText(bytes) {
    if (typeof $response !== "undefined" && typeof $response.body === "string") {
      return $response.body;
    }
    if (!bytes) return "";
    try {
      if (typeof TextDecoder !== "undefined") return new TextDecoder("utf-8").decode(bytes);
    } catch (_) {}
    let s = "";
    const limit = Math.min(bytes.length, 250000);
    for (let i = 0; i < limit; i++) s += String.fromCharCode(bytes[i]);
    return s;
  }

  function unique(arr) {
    const seen = Object.create(null);
    return arr.filter(x => {
      if (seen[x]) return false;
      seen[x] = true;
      return true;
    });
  }

  try {
    const url = (typeof $request !== "undefined" && $request.url) ? $request.url : "";
    let kind = "other";
    if (url.indexOf("/scrollsita/v1/scroll/") !== -1) kind = "scrollsita";
    else if (url.indexOf("recommendations-in-free-tier-playlist") !== -1) kind = "free-tier-recommendations";
    else if (url.indexOf("/ondemand-selector/v2/select-ondemand-set") !== -1) kind = "ondemand-selector";

    const bytes = bodyBytes();
    const text = bodyText(bytes);
    const uris = unique(text.match(/spotify:(?:track|playlist|album):[A-Za-z0-9]+/g) || []).slice(0, 30);

    const status = ($response && ($response.status || $response.statusCode)) || "n/a";
    const headers = ($response && $response.headers) || {};
    const ctKey = Object.keys(headers).find(k => k.toLowerCase() === "content-type");
    const ct = ctKey ? headers[ctKey] : "n/a";

    console.log(
      TAG +
      " response kind=" + kind +
      " status=" + status +
      " bytes=" + (bytes ? bytes.length : (typeof $response.body === "string" ? $response.body.length : 0)) +
      " contentType=" + ct +
      " uris=" + uris.length
    );

    if (uris.length) console.log(TAG + " response-uris " + uris.join(","));
  } catch (e) {
    console.log(TAG + " response ERROR " + String(e && e.message ? e.message : e));
  }

  $done({});
})();
