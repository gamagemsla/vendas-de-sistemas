import pathlib

template = open('c:/Users/gamag/OneDrive/Área de Trabalho/vendas-de-sistemas/template.txt', 'r', encoding='utf-8').read()
pathlib.Path('c:/Users/gamag/OneDrive/Área de Trabalho/vendas-de-sistemas/src/vendas/infrastructure/persistence/repositories.py').write_text(template, encoding='utf-8')
print('Done')