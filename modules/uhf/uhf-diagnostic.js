/*
 * UHF IPTV Player — пассивный диагностический логгер для Shadowrocket.
 *
 * Назначение:
 *   - собрать максимум полезной информации за один тестовый прогон;
 *   - НЕ изменять request/response;
 *   - логировать URL, method/status, headers и body;
 *   - текст/JSON печатать читаемо;
 *   - бинарные тела (protobuf/gRPC и т.п.) печатать как HEX + ASCII preview;
 *   - чувствительные токены/пароли не печатать целиком.
 *
 * Используется одновременно как http-request и http-response script.
 */

var TAG = "[UHF-DIAG]";
var TEXT_LIMIT = 131072;   // до 128 KiB текста на одно body
var BINARY_LIMIT = 65536;  // до 64 KiB бинарного body
var CHUNK = 7000;          // дробим лог, чтобы длинная строка не потерялась целиком

function logLine(s) {
  try {
    console.log(TAG + " " + String(s));
  } catch (e) {}
}

function logChunked(label, value) {
  var s = value == null ? "<null>" : String(value);
  var total = Math.max(1, Math.ceil(s.length / CHUNK));
  if (s.length === 0) {
    logLine(label + " <empty>");
    return;
  }
  for (var i = 0; i < s.length; i += CHUNK) {
    var part = Math.floor(i / CHUNK) + 1;
    logLine(label + " [" + part + "/" + total + "] " + s.slice(i, i + CHUNK));
  }
}

function safeJson(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch (e) {
    try { return String(obj); } catch (_) { return "<unprintable>"; }
  }
}

function redactValue(key, value) {
  var k = String(key || "").toLowerCase();
  var v = value == null ? "" : String(value);

  if (
    k === "authorization" ||
    k === "proxy-authorization" ||
    k === "cookie" ||
    k === "set-cookie" ||
    k === "x-firebase-appcheck" ||
    k === "x-goog-api-key"
  ) {
    if (k === "authorization" && /^bearer\s+/i.test(v)) {
      return "<redacted bearer; " + describeJwt(v.replace(/^bearer\s+/i, "")) + ">";
    }
    return "<redacted; length=" + v.length + ">";
  }

  return value;
}

function sanitizedHeaders(headers) {
  var out = {};
  if (!headers || typeof headers !== "object") return out;
  try {
    Object.keys(headers).forEach(function (k) {
      out[k] = redactValue(k, headers[k]);
    });
  } catch (e) {
    return { error: String(e) };
  }
  return out;
}

function sanitizeUrl(url) {
  var s = String(url || "");
  // Google API key / auth-like query params не нужны для анализа, но являются секретами.
  return s.replace(/([?&](?:key|api_key|apikey|access_token|id_token|refresh_token|auth)=)[^&#]*/gi, "$1<redacted>");
}

function sanitizeText(text) {
  var s = String(text == null ? "" : text);

  // JSON-поля с credential/token значениями.
  s = s.replace(/("(?:access_token|id_token|refresh_token|token|password|authorization|app_check_token|appcheck_token)"\s*:\s*")[^"]*(")/gi, "$1<redacted>$2");

  // form-urlencoded варианты.
  s = s.replace(/((?:^|&)(?:access_token|id_token|refresh_token|token|password|authorization)=)[^&]*/gi, "$1<redacted>");

  return s;
}

function base64UrlDecode(s) {
  try {
    var t = String(s).replace(/-/g, "+").replace(/_/g, "/");
    while (t.length % 4) t += "=";
    if (typeof atob !== "function") return null;
    return atob(t);
  } catch (e) {
    return null;
  }
}

function describeJwt(token) {
  try {
    var parts = String(token || "").split(".");
    if (parts.length < 2) return "token length=" + String(token || "").length;
    var payload = base64UrlDecode(parts[1]);
    if (!payload) return "JWT length=" + String(token || "").length;
    var obj = JSON.parse(payload);
    var keep = {};
    ["iss", "aud", "sub", "iat", "exp", "auth_time", "user_id", "email", "email_verified", "firebase"].forEach(function (k) {
      if (Object.prototype.hasOwnProperty.call(obj, k)) keep[k] = obj[k];
    });
    return "JWT claims=" + JSON.stringify(keep);
  } catch (e) {
    return "JWT length=" + String(token || "").length;
  }
}

function bodyToBytes(body) {
  if (body == null || typeof body === "string") return null;

  try {
    if (typeof Uint8Array !== "undefined") {
      if (body instanceof Uint8Array) return body;
      if (body.buffer && typeof body.byteLength === "number") {
        return new Uint8Array(body.buffer, body.byteOffset || 0, body.byteLength);
      }
      if (typeof ArrayBuffer !== "undefined" && body instanceof ArrayBuffer) {
        return new Uint8Array(body);
      }
    }
  } catch (e) {}

  if (typeof body.length === "number") {
    try {
      var arr = [];
      for (var i = 0; i < body.length; i++) arr.push(Number(body[i]) & 255);
      return arr;
    } catch (e2) {}
  }

  return null;
}

function bytesLength(bytes) {
  try { return bytes.length; } catch (e) { return 0; }
}

function bytesPreview(bytes, limit) {
  var n = Math.min(bytesLength(bytes), limit);
  var hex = [];
  var ascii = [];

  for (var i = 0; i < n; i++) {
    var b = Number(bytes[i]) & 255;
    var h = b.toString(16);
    if (h.length < 2) h = "0" + h;
    hex.push(h);
    ascii.push(b >= 32 && b <= 126 ? String.fromCharCode(b) : ".");
  }

  return {
    shown: n,
    total: bytesLength(bytes),
    truncated: bytesLength(bytes) > n,
    hex: hex.join(""),
    ascii: ascii.join("")
  };
}

function dumpBody(label, body) {
  if (body == null) {
    logLine(label + " = <none>");
    return;
  }

  if (typeof body === "string") {
    var clean = sanitizeText(body);
    var clipped = clean.length > TEXT_LIMIT ? clean.slice(0, TEXT_LIMIT) : clean;
    logLine(label + " type=text chars=" + clean.length + (clean.length > TEXT_LIMIT ? " TRUNCATED" : ""));

    // Если это JSON, печатаем pretty JSON, иначе сырой текст.
    try {
      var parsed = JSON.parse(clipped);
      logChunked(label + " JSON", sanitizeText(safeJson(parsed)));
    } catch (e) {
      logChunked(label + " TEXT", clipped);
    }
    return;
  }

  var bytes = bodyToBytes(body);
  if (bytes) {
    var p = bytesPreview(bytes, BINARY_LIMIT);
    logLine(label + " type=binary bytes=" + p.total + " shown=" + p.shown + (p.truncated ? " TRUNCATED" : ""));
    logChunked(label + " HEX", p.hex);
    logChunked(label + " ASCII", p.ascii);
    return;
  }

  logLine(label + " type=" + typeof body);
  logChunked(label + " OBJECT", sanitizeText(safeJson(body)).slice(0, TEXT_LIMIT));
}

function dumpRequest(req, includeBody) {
  if (!req) {
    logLine("REQUEST=<missing>");
    return;
  }
  logLine("REQUEST method=" + String(req.method || "") + " url=" + sanitizeUrl(req.url || ""));
  logChunked("REQUEST HEADERS", safeJson(sanitizedHeaders(req.headers)));
  if (includeBody) dumpBody("REQUEST BODY", req.body);
}

function dumpResponse(resp) {
  if (!resp) {
    logLine("RESPONSE=<missing>");
    return;
  }
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

// Строго пассивный режим: ничего не меняем и не блокируем.
$done({});
