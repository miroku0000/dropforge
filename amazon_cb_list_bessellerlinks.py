# List of 500+ Amazon Browse Node IDs (truncated here)
NODE_IDS = [
    172282,  # Electronics
    1055398,  # Home
    1040660,  # Clothing
    165793011,  # Toys
    # Add more from the resources above
]


def generate_bestseller_urls():
    return [f"https://www.amazon.com/gp/bestsellers/{node}" for node in NODE_IDS]


if __name__ == "__main__":
    urls = generate_bestseller_urls()
    for url in urls:
        print(url)
