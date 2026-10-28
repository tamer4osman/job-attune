import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Standalone output for the container images (see Dockerfile); the same
  // build is used locally. Type errors fail the build - they are a release
  // gate in CI (tsc --noEmit) and the only type gate inside Docker, where
  // no separate tsc step runs.
  output: "standalone",
  // Pin the file-tracing root to this project so the standalone layout is
  // deterministic (.next/standalone/server.js, not nested under a workspace
  // folder) even when the repo is checked out inside a parent directory
  // that looks like a workspace root (has its own package.json/lockfile).
  outputFileTracingRoot: path.join(__dirname),
  reactStrictMode: false,
};

export default nextConfig;
