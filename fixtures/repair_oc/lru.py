class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.data = {}
        self.order = []

    def get(self, key):
        if key not in self.data:
            return None
        # Move accessed key to the most recent position
        self.order.remove(key)
        self.order.append(key)
        return self.data[key]

    def put(self, key, value):
        if key in self.data:
            self.order.remove(key)
        self.data[key] = value
        self.order.append(key)
        if len(self.order) > self.capacity:
            oldest = self.order.pop(0)
            del self.data[oldest]
