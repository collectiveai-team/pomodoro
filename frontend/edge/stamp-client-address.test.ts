// @vitest-environment node
import { createServer, request as httpRequest } from "node:http";
import type { AddressInfo } from "node:net";
import { describe, expect, it } from "vitest";
import "./stamp-client-address.cjs";

function forwardedForSeenBehind(forgedHeader: string | undefined): Promise<string | undefined> {
  return new Promise((resolve, reject) => {
    const server = createServer((req, res) => {
      res.end(req.headers["x-forwarded-for"] ?? "");
    });
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address() as AddressInfo;
      const headers = forgedHeader ? { "X-Forwarded-For": forgedHeader } : {};
      const req = httpRequest({ host: "127.0.0.1", port, headers }, (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          server.close();
          resolve(body || undefined);
        });
      });
      req.on("error", reject);
      req.end();
    });
  });
}

describe("stamp-client-address preload", () => {
  it("replaces a client-supplied X-Forwarded-For with the socket address", async () => {
    const seen = await forwardedForSeenBehind("203.0.113.7, 198.51.100.1");

    expect(seen).toMatch(/^(::ffff:)?127\.0\.0\.1$/);
  });

  it("sets X-Forwarded-For to the socket address when the client sent none", async () => {
    const seen = await forwardedForSeenBehind(undefined);

    expect(seen).toMatch(/^(::ffff:)?127\.0\.0\.1$/);
  });
});
