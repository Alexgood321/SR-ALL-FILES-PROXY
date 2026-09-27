/*
 * UHF IPTV Player — пассивная диагностика Sync / Entitlement для Shadowrocket.
 *
 * Ничего не блокирует и не изменяет. Пишет доступные request/response данные,
 * маскирует credential/token значения и отдельно выделяет признаки подписки/sync.
 */

var TAG = "[UHF-SYNC-DIAG]";
var TEXT_LIMIT = 131072;
var BINARY_LIMIT = 65536;
var CHUNK = 7000;
var INTEREST = /(?:premium|\bpro\b|subscription|subscriber|entitlement|purchase|purchased|product|plan|trial|expire|expiration|renew|receipt|feature|sync|cloud|icloud|family|watermark|\bads?\b|active|enabled)/i;

function logLine(s) {
  try { console.log(TAG + " " + String(s)); } catch (_) {}
}

function logChunked(label, value) {
  var s = value == null ? "<null>" : String(value);
  if (!s.length) { logLine(label + " <empty>"); return; }
  var total = Math.ceil(s.length / CHUNK);
  for (var i = 0; i < s.length; i += CHUNK) {
    logLine(label + " [" + (Math.floor(i / CHUNK) + 1) + "/" + total + "] " + s.slice(i, i + CHUNK));
  }
}

function safeJson(v) {
  try { return JSON.stringify(v, null, 2); } catch (_) { return String(v); }
}

function base64UrlDecode(s) {
  try {
    var t = String(s).replace(/-/g, "+").replace(/_/g, "/");
    while (t.length % 4) t += "=";
    return typeof atob === "function" ? atob(t) : null;
  } catch (_) { return null; }
}

function jwtSummary(token) {
  try {
    var parts = String(token || "").split(".");
    if (parts.length < 2) return "token length=" + String(token || "").length;
    var raw = base64UrlDecode(parts[1]);
    if (!raw) return "JWT length=" + String(token || "").length;
    var obj = JSON.parse(raw);
    var out = {};
    ["iss", "aud", "iat", "exp", "auth_time", "firebase"].forEach(function (k) {
      if (Object.prototype.hasOwnProperty.call(obj, k)) out[k] = obj[k];
    });
    Object.keys(obj).forEach(function (k) {
      if (INTEREST.test(k) && !Object.prototype.hasOwnProperty.call(out, k)) out[k] = obj[k];
    });
    return "JWT claims=" + JSON.stringify(out);
  } catch (_) { return "JWT length=" + String(token || "").length; }
}

function redactHeader(key, value) {
  var k = String(key || "").toLowerCase();
  var v = value == null ? "" : String(value);
  if (k === "authorization" && /^bearer\s+/i.test(v)) {
    return "<redacted bearer; " + jwtSummary(v.replace(/^bearer\s+/i, "")) + ">";
  }
  if (["authorization", "proxy-authorization", "cookie", "set-cookie", "x-firebase-appcheck", "x-goog-api-key"].indexOf(k) >= 0) {
    return "<redacted; length=" + v.length + ">";
  }
  return value;
}

function sanitizedHeaders(headers) {
  var out = {};
  if (!headers || typeof headers !== "object") return out;
  try { Object.keys(headers).forEach(function (k) { out[k] = redactHeader(k, headers[k]); }); }
  catch (e) { return { error: String(e) }; }
  return out;
}

function sanitizeUrl(url) {
  return String(url || "").replace(/([?&](?:key|api_key|apikey|access_token|id_token|refresh_token|auth)=)[^&#]*/gi, "$1<redacted>");
}

function sanitizeText(text) {
  var s = String(text == null ? "" : text);
  s = s.replace(/("(?:access_token|id_token|refresh_token|token|password|authorization|app_check_token|appcheck_token)"\s*:\s*")[^"]*(")/gi, "$1<redacted>$2");
  s = s.replace(/((?:^|&)(?:access_token|id_token|refresh_token|token|password|authorization)=)[^&]*/gi, "$1<redacted>");
  s = s.replace(/((?:^|[?&])(?:key|api_key|apikey)=)[^&#\s]*/gi, "$1<redacted>");
  return s;
}

function interestingLines(text) {
  var s = sanitizeText(text);
  var parts = s.split(/[\r\n]+|(?=[,{])/);
  var hits = [];
  for (var i = 0; i < parts.length && hits.length < 80; i++) {
    var p = parts[i].trim();
    if (p && INTEREST.test(p)) hits.push(p.slice(0, 1200));
  }
  if (hits.length) logChunked("INTEREST", hits.join("\n"));
}

function bodyToBytes(body) {
  if (body == null || typeof body === "string") return null;
  try {
    if (typeof Uint8Array !== "undefined") {
      if (body instanceof Uint8Array) return body;
      if (body.buffer && typeof body.byteLength === "number") return new Uint8Array(body.buffer, body.byteOffset || 0, body.byteLength);
      if (typeof ArrayBuffer !== "undefined" && body instanceof ArrayBuffer) return new Uint8Array(body);
    }
  } catch (_) {}
  try {
    if (typeof body.length === "number") {
      var a = [];
      for (var i = 0; i < body.length; i++) a.push(Number(body[i]) & 255);
      return a;
    }
  } catch (_) {}
  return null;
}

function binaryPreview(bytes) {
  var total = bytes.length || 0;
  var n = Math.min(total, BINARY_LIMIT);
  var hex = [];
  var ascii = [];
  var printable = [];
  var run = "";
  for (var i = 0; i < n; i++) {
    var b = Number(bytes[i]) & 255;
    var h = b.toString(16); if (h.length < 2) h = "0" + h;
    hex.push(h);
    ascii.push(b >= 32 && b <= 126 ? String.fromCharCode(b) : ".");
    if (b >= 32 && b <= 126) run += String.fromCharCode(b);
    else {
      if (run.length >= 4) printable.push(run);
      run = "";
    }
  }
  if (run.length >= 4) printable.push(run);
  return { total: total, shown: n, hex: hex.join(""), ascii: ascii.join(""), printable: printable.join("\n") };
}

function dumpBody(label, body) {
  if (body == null) { logLine(label + " = <none>"); return; }
  if (typeof body === "string") {
    var clean = sanitizeText(body);
    var clipped = clean.slice(0, TEXT_LIMIT);
    logLine(label + " type=text chars=" + clean.length + (clean.length > TEXT_LIMIT ? " TRUNCATED" : ""));
    try {
      var parsed = JSON.parse(clipped);
      var pretty = sanitizeText(safeJson(parsed));
      logChunked(label + " JSON", pretty);
      interestingLines(pretty);
    } catch (_) {
      logChunked(label + " TEXT", clipped);
      interestingLines(clipped);
    }
    return;
  }
  var bytes = bodyToBytes(body);
  if (bytes) {
    var p = binaryPreview(bytes);
    logLine(label + " type=binary bytes=" + p.total + " shown=" + p.shown + (p.total > p.shown ? " TRUNCATED" : ""));
    logChunked(label + " HEX", p.hex);
    logChunked(label + " ASCII", p.ascii);
    if (p.printable) {
      logChunked(label + " PRINTABLE", sanitizeText(p.printable));
      interestingLines(p.printable);
    }
    return;
  }
  var obj = sanitizeText(safeJson(body)).slice(0, TEXT_LIMIT);
  logChunked(label + " OBJECT", obj);
  interestingLines(obj);
}

function dumpRequest(req, withBody) {
  if (!req) { logLine("REQUEST=<missing>"); return; }
  logLine("REQUEST method=" + String(req.method || "") + " url=" + sanitizeUrl(req.url || ""));
  logChunked("REQUEST HEADERS", safeJson(sanitizedHeaders(req.headers)));
  if (withBody) dumpBody("REQUEST BODY", req.body);
}

function dumpResponse(resp) {
  if (!resp) { logLine("RESPONSE=<missing>"); return; }
  var status = resp.statusCode != null ? resp.statusCode : (resp.status != null ? resp.status : "");
  logLine("RESPONSE status=" + String(status));
  logChunked("RESPONSE HEADERS", safeJson(sanitizedHeaders(resp.headers)));
  dumpBody("RESPONSE BODY", resp.body);
}

try {
  var isResponse = typeof $response !== "undefined" && $response != null;
  logLine("================ " + (isResponse ? "HTTP RESPONSE" : "HTTP REQUEST") + " ================");
  dumpRequest(typeof $request !== "undefined" ? $request : null, !isResponse);
  if (isResponse) dumpResponse($response);
  logLine("================ END ================");
} catch (e) {
  logLine("LOGGER ERROR: " + String(e && e.stack ? e.stack : e));
}

$done({});
