from app.graph import graph


def main():
    url = input("URL: ").strip()
    result = graph.invoke({"url": url})
    print(result["html"])


if __name__ == "__main__":
    main()
