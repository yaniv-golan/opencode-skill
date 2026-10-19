# Spec

## `slugify(str, { separator = "-", lowercase = true } = {})` in text.js
- Normalize with NFKD and drop combining marks, so `é` becomes `e`.
- Replace every run of characters other than ASCII letters and digits with `separator`.
- Trim `separator` from both ends. Lowercase unless `lowercase` is false.
- A non-string argument throws `TypeError`.
- `"Héllo, Wörld!"` → `"hello-world"`, `"  a--b  "` → `"a-b"`, `("Foo Bar", { separator: "_" })` →
  `"foo_bar"`, `("Foo Bar", { lowercase: false })` → `"Foo-Bar"`, `"!!!"` → `""`.

## `class LRUCache` in cache.js
- `new LRUCache(capacity)`: capacity is a positive integer, else `RangeError`.
- `get(key)`: the value, or `undefined`; a hit makes the key most recently used.
- `set(key, value)`: inserts or updates (an update also makes it most recently used), evicts the least
  recently used key when the size would exceed capacity, and returns the cache.
- `has(key)`: boolean; does not change recency. `delete(key)`: true if it was present.
- `size` (getter): the number of entries. `keys()`: an array from least to most recently used.
