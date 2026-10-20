from lru import LRUCache

c = LRUCache(2)
c.put("a", 1)
c.put("b", 2)
assert c.get("a") == 1
c.put("c", 3)
assert c.get("b") is None, "b should be evicted (a was recently used)"
assert c.get("a") == 1
assert c.get("c") == 3
c.put("a", 10)
c.put("d", 4)
assert c.get("c") is None
assert c.get("a") == 10
print("OK")
