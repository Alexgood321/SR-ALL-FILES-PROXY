// LOCAL PATCH — Spotify playback-path request diagnostic (2026-09-27).
// Read-only except for the SAME narrow timezone alignment already used by the
// main module: Europe/Moscow -> Europe/Helsinki in timezone headers/query.
// It logs which playback/free-tier path the iOS client asks for.

(function () {
  const TAG = "[Spotify Playback Path]";
  const req = typeof $request !== "undefined" ? $request : {};
  const originalUrl = req.url || "";
  let url = originalUrl;
  const headers = Object.assign({}, req.headers || {});

  function headerKey(name) {
    const want = name.toLowerCase();
    return Object.keys(headers).find(k => k.toLowerCase() === want) || null;
  }

  let headerChanged = false;
  ["Time-Zone", "X-Client-Timezone"].forEach(name => {
    const k = headerKey(name);
    if (k && typeof headers[k] === "string" && headers[k].indexOf("Europe/Moscow") !== -1) {
      headers[k] = headers[k].replace(/Europe\/Moscow/g, "Europe/Helsinki");
      headerChanged = true;
    }
  });

  let urlChanged = false;
  if (url.indexOf("Europe/Moscow") !== -1 || url.indexOf("Europe%2FMoscow") !== -1) {
    url = url
      .replace(/Europe\/Moscow/g, "Europe/Helsinki")
      .replace(/Europe%2FMoscow/gi, "Europe%2FHelsinki");
    urlChanged = url !== originalUrl;
  }

  let kind = "other";
  if (originalUrl.indexOf("/scrollsita/v1/scroll/") !== -1) kind = "scrollsita";
  else if (originalUrl.indexOf("recommendations-in-free-tier-playlist") !== -1) kind = "free-tier-recommendations";
  else if (originalUrl.indexOf("/ondemand-selector/v2/select-ondemand-set") !== -1) kind = "ondemand-selector";

  function queryValue(name) {
    const m = originalUrl.match(new RegExp("[?&]" + name + "=([^&]*)", "i"));
    if (!m) return "";
    try { return decodeURIComponent(m[1]); } catch (_) { return m[1]; }
  }

  let track = "";
  const tm = originalUrl.match(/\/scrollsita\/v1\/scroll\/(spotify:track:[A-Za-z0-9]+)/i);
  if (tm) track = tm[1];

  const context = queryValue("play_context_uri") || queryValue("contextUri") || "";
  const signal = queryValue("signal") || "";
  const region = queryValue("region") || "";

  console.log(
    TAG +
    " request kind=" + kind +
    " track=" + (track || "n/a") +
    " context=" + (context || "n/a") +
    " signal=" + (signal || "n/a") +
    " region=" + (region || "n/a") +
    " tzHeader=" + headerChanged +
    " tzUrl=" + urlChanged
  );

  const out = {};
  if (urlChanged) out.url = url;
  if (headerChanged) out.headers = headers;
  $done(out);
})();
