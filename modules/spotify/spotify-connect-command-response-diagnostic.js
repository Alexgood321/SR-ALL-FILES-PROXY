// LOCAL PATCH — Spotify Connect player-command response diagnostic.
// Purpose: correlate each seek/skip/play command with the server response.
// Diagnostic only: response bytes and headers are never modified.

(() => {
  const TAG = "[Spotify Command Response]";

  function getHeader(headers, wanted) {
    const lower = wanted.toLowerCase();
    for (const key of Object.keys(headers || {})) {
      if (key.toLowerCase() === lower) return String(headers[key]);
    }
    return "";
  }

  function bodyLength() {
    const body = (typeof $response.bodyBytes !== "undefined" && $response.bodyBytes)
      ? $response.bodyBytes
      : $response.body;
    if (body == null) return 0;
    if (typeof body === "string") return body.length;
    if (body.byteLength != null) return body.byteLength;
    if (body.length != null) return body.length;
    return 0;
  }

  function extractIds(url) {
    const match = /\/connect-state\/v1\/player\/command\/from\/([^/?]+)\/to\/([^/?]+)/.exec(url || "");
    return match ? { from: match[1], to: match[2] } : { from: "?", to: "?" };
  }

  try {
    const ids = extractIds($request && $request.url ? $request.url : "");
    const headers = ($response && $response.headers) || {};
    const status = ($response && ($response.statusCode != null ? $response.statusCode : $response.status)) || "n/a";
    const contentType = getHeader(headers, "content-type") || "n/a";
    const contentLength = getHeader(headers, "content-length") || "n/a";
    const server = getHeader(headers, "server") || "n/a";

    console.log(
      `${TAG} status=${status}; from=${ids.from}; to=${ids.to}; ` +
      `bodyBytes=${bodyLength()}; contentLength=${contentLength}; contentType=${contentType}; server=${server}`
    );
  } catch (e) {
    console.log(`${TAG} diagnostic error: ${e && e.message ? e.message : e}`);
  }

  $done({});
})();
