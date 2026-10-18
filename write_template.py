import pathlib

lines = ["test"]
content = "\n".join(lines)
pathlib.Path("c:/Users/gamag/OneDrive/Área de Trabalho/vendas-de-sistemas/template.txt").write_text(content, encoding="utf-8")
print("ok")