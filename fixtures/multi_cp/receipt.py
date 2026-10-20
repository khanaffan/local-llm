from fmt import format_price


def receipt(items):
    lines = [f"{name}: {format_price(c)}" for name, c in items]
    lines.append(f"TOTAL: {format_price(sum(c for _, c in items))}")
    return "\n".join(lines)
