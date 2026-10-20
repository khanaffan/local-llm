from fmt import format_price
from receipt import receipt

assert format_price(500) == "$5.00"
assert format_price(1999) == "$19.99"
assert format_price(1234567) == "$12,345.67"
assert receipt([("tea", 350), ("cake", 1250)]) == "tea: $3.50\ncake: $12.50\nTOTAL: $16.00"
print("OK")
