/* UHF sync diagnostic scanner. Passive: never modifies traffic. */
var TAG = "[UHF-SYNC-SAFE]";
var INTEREST = /(?:sync|backup|cloud|icloud|feature|active|enabled|device|playlist)/i;

function log(s) { try { console.log(TAG + " " + String(s)); } catch (_) {} }

function redact(s) {
  s = String(s == null ? "" : s);
  s = s.replace(/\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b/g, "<redacted-jwt>");
  s = s.replace(/\b[A-Za-z0-9_+\/=.-]{80,}\b/g, "<redacted-long-value>");
  s = s.replace(/("(?:token|refreshToken|refresh_token|access_token|id_token|assertion|artifact|challenge|password)"\s*:\s*")[^"]*(")/gi, "$1<redacted>$2");
  return s;
}

function printable(body) {
  if (body == null) return "";
  if (typeof body === "string") return redact(body);
  var bytes = null;
  try {
    if (typeof Uint8Array !== "undefined" && body instanceof Uint8Array) bytes = body;
    else if (body && body.buffer && typeof body.byteLength === "number") bytes = new Uint8Array(body.buffer, body.byteOffset || 0, body.byteLength);
    else if (typeof body.length === "number") bytes = body;
  } catch (_) {}
  if (!bytes) return "";
  var out = [], run = "", n = Math.min(bytes.length || 0, 65536);
  for (var i = 0; i < n; i++) {
    var b = Number(bytes[i]) & 255;
    if (b >= 32 && b <= 126) run += String.fromCharCode(b);
    else { if (run.length >= 4) out.push(run); run = ""; }
  }
  if (run.length >= 4) out.push(run);
  return redact(out.join("\n"));
}

function hits(text) {
  var a = String(text || "").split(/[\r\n]+|(?=[,{])/), out = [];
  for (var i = 0; i < a.length && out.length < 60; i++) {
    var x = a[i].trim();
    if (x && INTEREST.test(x)) out.push(x.slice(0, 800));
  }
  return out;
}

try {
  var responseMode = typeof $response !== "undefined" && $response != null;
  var req = typeof $request !== "undefined" ? $request : null;
  if (req) log((responseMode ? "RESPONSE-FOR" : "REQUEST") + " " + String(req.method || "") + " " + String(req.url || "").replace(/([?&](?:key|token|auth)=)[^&#]*/gi, "$1<redacted>"));
  if (responseMode) log("STATUS " + String($response.statusCode != null ? $response.statusCode : ($response.status || "")));
  var body = responseMode ? $response.body : (req ? req.body : null);
  var found = hits(printable(body));
  if (found.length) log("HITS\n" + found.join("\n"));
} catch (e) { log("ERROR " + String(e)); }

$done({});
