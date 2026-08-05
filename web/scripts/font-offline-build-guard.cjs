"use strict";
/* eslint-disable @typescript-eslint/no-require-imports */

const net = require("node:net");
const tls = require("node:tls");

const isLoopback = (host) =>
  host === "localhost" ||
  host === "127.0.0.1" ||
  host === "::1" ||
  host === "[::1]";

const assertOfflineTarget = (options, fallbackHost) => {
  const host =
    typeof options === "string"
      ? options
      : options && typeof options === "object"
        ? options.host
        : fallbackHost;
  if (host && !isLoopback(host)) {
    throw new Error(`network access is disabled for the offline font build: ${host}`);
  }
};

const originalNetConnect = net.connect;
const originalCreateConnection = net.createConnection;
const originalTlsConnect = tls.connect;

net.connect = function guardedConnect(...args) {
  assertOfflineTarget(args[0], args[1]);
  return originalNetConnect.apply(this, args);
};
net.createConnection = function guardedCreateConnection(...args) {
  assertOfflineTarget(args[0], args[1]);
  return originalCreateConnection.apply(this, args);
};
tls.connect = function guardedTlsConnect(...args) {
  assertOfflineTarget(args[0], args[1]);
  return originalTlsConnect.apply(this, args);
};

const blockedFetch = () => {
  throw new Error("network access is disabled for the offline font build");
};

if (typeof globalThis.fetch === "function") {
  globalThis.fetch = blockedFetch;
}
