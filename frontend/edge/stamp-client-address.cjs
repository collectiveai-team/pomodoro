// Preloaded ahead of Next's standalone server with `node --require` (see Dockerfile).
//
// The frontend is the edge: browsers connect to it directly and it proxies `/api/*` to the
// backend. Next keeps a client-supplied `X-Forwarded-For` as it is and only fills the header from
// the socket when it is missing, so a browser could choose the IP the backend's login rate limit
// keys on. Overwriting the header with the socket address before Next sees the request makes it
// the one address the client cannot write; the backend reads the rightmost entry
// (backend/pomodoro/api/v1/auth/client_ip.py). Behind another proxy this would key every user on
// that proxy's address, so revisit it if a load balancer is ever put in front of the frontend.
const http = require("node:http");

function stampClientAddress(req) {
  const address = req.socket?.remoteAddress;
  if (address) {
    req.headers["x-forwarded-for"] = address;
  } else {
    delete req.headers["x-forwarded-for"];
  }
}

const emit = http.Server.prototype.emit;
http.Server.prototype.emit = function emitWithClientAddress(event, req, ...rest) {
  if (event === "request") {
    stampClientAddress(req);
  }
  return emit.call(this, event, req, ...rest);
};

module.exports = { stampClientAddress };
