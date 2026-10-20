def format_price(cents):
    dollars = cents / 100
    return f"${dollars:,.2f}"
