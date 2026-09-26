// LOCAL PATCH — Spotify Gabo playback A/B test.
// Purpose: test whether Spotify's gabo playback/event telemetry participates
// in the seek -> next-track bug observed on recent iOS Spotify builds.
//
// Scope is intentionally narrow:
//   - only requests matched by /gabo-receiver-service/
//   - returns a local empty HTTP 200 response
//   - does not modify account attributes, playback APIs, audio CDN, timezone,
//     request bodies, cookies, authorization headers or Spotify Connect state
//
// This is an experiment. If it does not change playback behavior, remove the
// matching rule from Spotify-Config.sgmodule and this file can be deleted.

(() => {
  console.log("[Spotify Gabo A/B] LOCAL PATCH: returning empty 200");

  $done({
    response: {
      status: 200,
      headers: {
        "cache-control": "no-cache",
        "content-length": "0",
        "content-type": "application/octet-stream"
      },
      body: ""
    }
  });
})();
