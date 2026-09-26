// Spotify timezone alignment patch for Shadowrocket.
// LOCAL PATCH (Alexgood321 / SR-ALL-FILES-PROXY):
// Purpose: align Spotify's explicit client timezone with the Finland proxy exit.
// Scope is intentionally narrow: only Europe/Moscow -> Europe/Helsinki.
// It changes:
//   1) request header: Time-Zone
//   2) request header: X-Client-Timezone (if Spotify starts sending it)
//   3) query parameter: timezone
//   4) query parameter: client-timezone
// No other headers, body fields, locale, account country or GPS values are touched.

(() => {
  const FROM = "Europe/Moscow";
  const TO = "Europe/Helsinki";

  let url = $request.url;
  const headers = Object.assign({}, $request.headers || {});
  let headerChanged = false;
  let urlChanged = false;

  // LOCAL PATCH: replace only explicit Spotify timezone headers.
  for (const key of Object.keys(headers)) {
    if (/^(time-zone|x-client-timezone)$/i.test(key) && String(headers[key]).toLowerCase() === FROM.toLowerCase()) {
      headers[key] = TO;
      headerChanged = true;
    }
  }

  // LOCAL PATCH: replace only explicit timezone query parameters.
  // Handles both encoded and unencoded slash forms.
  const replaceTimezoneParam = (input, name) => {
    const re = new RegExp(`([?&])${name}=Europe(?:%2F|/)Moscow(?=(&|$))`, "gi");
    const output = input.replace(re, `$1${name}=Europe%2FHelsinki`);
    if (output !== input) urlChanged = true;
    return output;
  };

  url = replaceTimezoneParam(url, "timezone");
  url = replaceTimezoneParam(url, "client-timezone");

  if (headerChanged || urlChanged) {
    console.log(`[Spotify TZ Patch] ${FROM} -> ${TO}; header=${headerChanged}; url=${urlChanged}`);
    $done({ url, headers });
    return;
  }

  $done({});
})();
