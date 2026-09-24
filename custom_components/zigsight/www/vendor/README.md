# Vendored frontend libraries

These files are served by the integration from `/zigsight_static/vendor/` so
the ZigSight panel and cards work without internet access. Do not edit them;
update them by downloading a new release and adjusting this file.

| File | Library | Version | Source | License |
|------|---------|---------|--------|---------|
| `lit-core.min.js` | [Lit](https://lit.dev) (core bundle: `LitElement`, `html`, `svg`, `css`, `nothing`) | 3.3.3 | `https://cdn.jsdelivr.net/gh/lit/dist@3.3.3/core/lit-core.min.js` (official pre-built bundle of the [lit/dist](https://github.com/lit/dist) repository) | BSD-3-Clause, see `LICENSE-lit` (from the `lit@3.3.3` npm package) |

Only change made to the upstream file: the trailing
`//# sourceMappingURL=lit-core.min.js.map` comment was removed (the map is
not vendored; the comment only caused 404s with the developer tools open).

Upstream SHA-256 (before removing the comment):
`f607f470475d8ab790754cb70f72cdbe2390c4a57ab59df6cdb360eeb72bd87c`.

To update:

```bash
VERSION=3.3.3
curl -fsSL "https://cdn.jsdelivr.net/gh/lit/dist@${VERSION}/core/lit-core.min.js" \
  | grep -v '^//# sourceMappingURL' > lit-core.min.js
npm pack "lit@${VERSION}" && tar -xzf "lit-${VERSION}.tgz" package/LICENSE \
  && mv package/LICENSE LICENSE-lit && rm -rf package "lit-${VERSION}.tgz"
```

The topology graph does not use a graph library (such as vis-network): it is
a small SVG renderer in `../lib/topology-graph.js` with the layouts in
`../lib/layout.js`.
