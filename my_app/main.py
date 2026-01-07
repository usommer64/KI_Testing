import modal

app = modal.App("my-test-app")

@app.function()
def hello(name: str = "World"):
    return f"Hello, {name}!"

@app. local_entrypoint()
def main():
    result = hello. remote("Modal")
    print(result)